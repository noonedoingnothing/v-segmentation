from stemseg.config import cfg
from stemseg.utils import transforms
from stemseg.data.generic_video_dataset_parser import parse_generic_video_dataset,parse_generic_video_dataset_limit
from stemseg.data.common import compute_resize_params, scale_and_normalize_images
from stemseg.data.image_to_seq_augmenter import ImageToSeqAugmenter

from torch.utils.data import Dataset

import numpy as np
import random
import torch
import torch.nn.functional as F

from os import path

import imgaug
import imgaug.augmenters as iaa
from imgaug.augmentables.segmaps import SegmentationMapsOnImage
from datetime import datetime
import cv2
from os.path import exists

class VideoDataset(Dataset):
    def __init__(self, base_dir, vds_json, clip_length, apply_augmentations, **kwargs):
        super().__init__()

        temp = vds_json.replace('youtube_vis_train.json','');
        temp = temp.replace('youtube_vis_val.json','');
    
        if path.isdir(temp+'limit'):
            self.sequences, self.meta_info = parse_generic_video_dataset_limit(base_dir, vds_json)
        else:
            self.sequences, self.meta_info = parse_generic_video_dataset(base_dir, vds_json)


        self.clip_length = clip_length
        self.apply_augmentations = apply_augmentations

        self.np_to_tensor = transforms.BatchImageTransform(
            transforms.ToTorchTensor(format='CHW')
        )

        if self.clip_length == 2:
            self.augmenter = ImageToSeqAugmenter(
                perspective=kwargs.get("perspective_transform", False),
                affine=kwargs.get("affine_transform", True),
                motion_blur=kwargs.get("motion_blur", True),
                motion_blur_prob=kwargs.get("motion_blur_prob", 0.3),
                motion_blur_kernel_sizes=kwargs.get("motion_blur_kernel_sizes", (5, 7)),
                scale_range=kwargs.get("scale_range", (0.8, 1.2)),
                rotation_range=kwargs.get("rotation_range", (-15, 15))
            )
        else:
            self.augmenter = ImageToSeqAugmenter(
                perspective=kwargs.get("perspective_transform", False),
                affine=kwargs.get("affine_transform", False),
                motion_blur=kwargs.get("motion_blur", False),
                motion_blur_prob=kwargs.get("motion_blur_prob", 0.3),
                motion_blur_kernel_sizes=kwargs.get("motion_blur_kernel_sizes", (5, 7)),
                scale_range=kwargs.get("scale_range", (0.9, 1.1)),
                rotation_range=kwargs.get("rotation_range", (-7, 7)),
                translate_range=kwargs.get("translation_range", {"x": (-0.1, 0.1), "y": (-0.1, 0.1)})
            )

    def filter_zero_instance_frames(self):
        for seq in self.sequences:
            seq.filter_zero_instance_frames()

        self.sequences = [seq for seq in self.sequences if len(seq) > 0]

    def filter_categories(self, cat_ids_to_keep):
        for seq in self.sequences:
            seq.filter_categories(cat_ids_to_keep)

        self.sequences = [seq for seq in self.sequences if len(seq) > 0]

    def parse_sample_at(self, idx):
        raise NotImplementedError("This method must be implemented by the derived class.")

    def __getitem__(self, index):
        images, masks, category_labels, meta_info = self.parse_sample_at(index)  # masks: BinaryMaskSequenceList

        ignore_masks = meta_info['ignore_masks']

        image_height, image_width = images[0].shape[:2]

        # apply random horizontal flip and frame sequence reversal in training mode
        images, masks, ignore_masks = self.apply_random_flip(images, masks, ignore_masks)


        # introduce small augmentations (affine, brightness/hue) to the images
        images, masks, ignore_masks, invalid_pts_mask = self.apply_random_augmentation(images, masks, ignore_masks)

        # apply invalid points mask
        for t in range(self.clip_length):
            images[t] = np.where(invalid_pts_mask[t][..., None], 0, images[t])

        # reverse the sequence randomly
        images, masks, ignore_masks = self.apply_random_sequence_reversal(images, masks, ignore_masks)

        # compute scale factor for mask resizing
        new_width, new_height, scale_factor = compute_resize_params(images[0], cfg.INPUT.MIN_DIM, cfg.INPUT.MAX_DIM)

        # convert images to torch Tensors
        images = torch.stack(self.np_to_tensor(*images), 0).float()

        # resize and pad images images
        images = F.interpolate(images, (new_height, new_width), mode='bilinear', align_corners=False)

        # scale and normalize images
        images = scale_and_normalize_images(images, cfg.INPUT.IMAGE_MEAN, cfg.INPUT.IMAGE_STD, not cfg.INPUT.BGR_INPUT,
                                            cfg.INPUT.NORMALIZE_TO_UNIT_SCALE)

        # resize masks
        masks = masks.resize((new_width, new_height), None)


        ignore_masks = [mask.resize((new_height, new_width)) for mask in ignore_masks]

        masks = masks.tensor().permute(1, 0, 2, 3)                            # [N, T, H, W]
        ignore_masks = torch.stack([mask.tensor() for mask in ignore_masks], 0)  # [T, H, W]


        

        if random.random() < 0.5:
          scale_range=1.0; translate_range={"x": (-0.15, 0.15), "y": (-0.15, 0.15)}; rotation_range=(-20, 20)
          aug = iaa.Affine(scale=scale_range,translate_percent=translate_range,rotate=rotation_range,order=1,backend='auto')
          seed = int(datetime.now().strftime('%M%S%f')[-8:])
          imgq=[];mskq=[]
          for i in range(images.size(0)):
            imgaug.seed(seed)
            f = torch.permute(images[i],(1,2,0)).detach().cpu().numpy()
            faug = aug.augment_image(f)
            imgaug.seed(seed)
            m = torch.permute(masks[:,i,:,:],(1,2,0)).detach().cpu().numpy()
            maug = aug.augment_image(m)
            #print('maug',maug.shape)
            """
            file_exists = exists('/content/'+str(i)+'.png')
            if file_exists==False:
              cv2.imwrite('/content/'+str(i)+'.png',faug)
              for j in range(0,maug.shape[2]):
                cv2.imwrite('/content/'+str(i)+'_'+str(j)+'.png',maug[:,:,j]*255)
            """
            imgq.append(faug)
            mskq.append(maug)
          images = torch.permute(torch.tensor(np.asarray(imgq)),(0,3,1,2)).float()
          masks = torch.permute(torch.tensor(np.asarray(mskq)),(3,0,1,2)).float()


        targets = {
            "masks": masks,
            "category_ids": torch.tensor(category_labels, dtype=torch.long),
            "ignore_masks": ignore_masks
        }

        return images, targets, (image_width, image_height), meta_info

    def apply_random_flip(self, images, masks, ignore_masks):
        if self.apply_augmentations and random.random() < 0.5:
            images = [np.flip(image, axis=1) for image in images]
            masks = masks.flip_horizontal()
            ignore_masks = [mask.flip_horizontal() for mask in ignore_masks]

        return images, masks, ignore_masks

    def apply_random_sequence_reversal(self, images, masks, ignore_masks):
        if self.apply_augmentations and random.random() < 0.5:
            images = images[::-1]
            masks = masks.reverse()
            ignore_masks = ignore_masks[::-1]

        return images, masks, ignore_masks

    def apply_random_augmentation(self, images, masks, ignore_masks):
        if self.apply_augmentations:
            augmented_images, augmented_masks, augmented_ignore_masks, invalid_pts_mask = [], [], [], []

            for t in range(self.clip_length):
                concat_masks = masks._mask_sequence_list[t] + [ignore_masks[t]]
                augmented_image, augmented_masks_t, invalid_pts_mask_t = self.augmenter(images[t], concat_masks)
                augmented_masks_t, augmented_ignore_mask_t = augmented_masks_t[:-1], augmented_masks_t[-1]

                augmented_images.append(augmented_image)
                augmented_masks.append(augmented_masks)
                augmented_ignore_masks.append(augmented_ignore_mask_t)
                invalid_pts_mask.append(invalid_pts_mask_t)

            return augmented_images, augmented_masks, augmented_ignore_masks, invalid_pts_mask
        else:
            h, w = images[0].shape[:2]
            invalid_pts_mask = [np.zeros((h, w), np.uint8) for _ in range(self.clip_length)]
            return images, masks, ignore_masks, invalid_pts_mask
