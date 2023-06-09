from stemseg.utils import ModelOutputConsts, LossConsts
from stemseg.utils import distributed as dist_utils
from stemseg.modeling.losses._lovasz import LovaszHingeLoss

import torch
import torch.nn as nn
import torch.nn.functional as F
import datetime
import pickle
from os.path import exists
from pathlib import Path
import os
import glob
import shutil
import random
import numpy as np
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
import sklearn
from sklearn import metrics
from sklearn.cluster import DBSCAN


class EmbeddingLoss(nn.Module):
    def __init__(self, embedding_map_scale, **kwargs):
        super().__init__()
        kwargs = {k.lower(): v for k, v in kwargs.items()}

        self.embedding_map_scale = embedding_map_scale
        self.embedding_size = kwargs["embedding_size"]
        self.w_variance_smoothness = kwargs["weight_variance_smoothness"]
        self.w_lovasz = kwargs["weight_lovasz"]
        self.w_regularization = kwargs["weight_regularization"]
        self.w_seediness = kwargs["weight_seediness"]
        self.w = kwargs["weight"]
        self.n_free_dims = kwargs["nbr_free_dims"]

        assert len(kwargs["free_dim_stds"]) == self.n_free_dims, \
            "List of std values {} does not match number of free dims {}".format(len(kwargs["free_dim_stds"]), self.n_free_dims)

        if self.n_free_dims > 0:
            self.register_buffer("free_dim_bandwidths", 1. / torch.tensor(kwargs["free_dim_stds"]).float().unsqueeze(0) ** 2)  # [1, N_FREE_DIMS]

        self.lovasz_hinge_loss = LovaszHingeLoss()

        self.split_sizes = (self.embedding_size, self.embedding_size - self.n_free_dims, 1)
        self.num_input_channels = sum(self.split_sizes)
        paths  = str(Path().absolute())
        if 'content' in paths:
            self.currentpath = '/content/'
        if 'kaggle' in paths:
            self.currentpath = '/kaggle/working/'
            
    def clustermetric(self,instance_embeddings):
        instance_embeddingsz = []
        labels_true = []
        for n in range(len(instance_embeddings)):
            emb = instance_embeddings[n]
            labels_true.append(np.zeros((len(emb),1))+n)
            instance_embeddingsz.append(emb.detach().cpu().numpy())

        arr = np.vstack(instance_embeddingsz)
        
        db = DBSCAN(eps=0.1, min_samples=100).fit(arr)
        core_samples_mask = np.zeros_like(db.labels_, dtype=bool)
        core_samples_mask[db.core_sample_indices_] = True
        labels = db.labels_
        # Number of clusters in labels, ignoring noise if present.
        n_clusters_ = len(set(labels)) - (1 if -1 in labels else 0)
        n_noise_ = list(labels).count(-1)
        t_clusters = len(instance_embeddingsz)
        
        
        labels_true = np.vstack(labels_true).ravel()
        try:
          Homogeneity = metrics.homogeneity_score(labels_true, labels)
        except:
          Homogeneity=  0
          
        try:
          Completeness =  metrics.completeness_score(labels_true, labels)
        except:
          Completeness =0


        try:
          V_measure =  metrics.v_measure_score(labels_true, labels)
        except:
          V_measure = 0;


        try:
          Adjusted_Rand_Index = metrics.adjusted_rand_score(labels_true, labels)
        except:
          Adjusted_Rand_Index=0

        try:
          score_mutual = metrics.mutual_info_score(labels_true, labels)
        except:
          score_mutual=0

        try:
          score_fowlkes_mallows = metrics.fowlkes_mallows_score(labels_true, labels)
        except:
          score_fowlkes_mallows=0

        try:
          Silhouette =  metrics.silhouette_score(arr, labels)
        except:
          Silhouette =0

        try:
          Calinski = metrics.calinski_harabasz_score(arr, labels)
        except:
          Calinski=0

        try:
          Bouldin = metrics.davies_bouldin_score(arr, labels)
        except:
          Bouldin=0

        return [Homogeneity,Completeness,V_measure,Adjusted_Rand_Index,score_mutual,score_fowlkes_mallows,Silhouette,Calinski,Bouldin,n_clusters_,t_clusters,n_noise_]
        
            
        
        
  
    def logger(self,minute,now,metric,lovas,seed,total_loss):
        
        with open(self.currentpath+'Logger.pickle', 'rb') as handle:
            old_data = pickle.load(handle)
            
        shutil.copy(self.currentpath+'Logger.pickle',self.currentpath+'Logger_copy.pickle')
        with open(self.currentpath+'Logger.pickle', 'wb') as handle:
            
            new_data = [{'id':now , 'Homogeneity':metric[0], 'Completeness':metric[1], 'V_measure':metric[2], 'Adjusted_Rand_Index':metric[3], 'Mutual':metric[4],'Fowlkes':metric[5],'Silhouette':metric[6],'Calinski':metric[7],'Bouldin':metric[8],'pcluster':metric[9],'tcluster':metric[10],'noise':metric[11], 'lovas':lovas, 'seed':seed, 'total_loss':total_loss} ]
            data = old_data + new_data
            print(new_data)
            pickle.dump(data, handle, protocol=pickle.HIGHEST_PROTOCOL)
  
        for tfgpath in glob.iglob(os.path.join(self.currentpath, '*.tfg')):
            os.remove(tfgpath)
        with open(self.currentpath+str(minute)+'.tfg','w') as f:
            f.write('ff')
            
        
    def forward(self, embedding_map, targets, output_dict, *args, **kwargs):
        """
        Computes the embedding loss.
        :param embedding_map: Tensor of shape [N, C, T, H, W] (C = embedding dims + variance dims + seediness dims)
        :param targets: List (length N) of dicts, each containing a 'masks' field containing a tensor of
        shape (I (instances), T, H, W)
        :param output_dict: dict to populate with loss values.
        :return: Scalar loss
        """
        assert embedding_map.shape[1] == self.num_input_channels, "Expected {} channels in input tensor, got {}".format(
            self.num_input_channels, embedding_map.shape[1])

        embedding_map = embedding_map.permute(0, 2, 3, 4, 1)  # [N, T, H, W, C]

        embedding_map, bandwidth_map, seediness_map = embedding_map.split(self.split_sizes, dim=-1)
        assert bandwidth_map.shape[-1] + self.n_free_dims == embedding_map.shape[-1], \
            "Number of predicted bandwidth dims {} + number of free dims {} should equal number of total embedding " \
            "dims {}".format(bandwidth_map.shape[-1], self.n_free_dims, embedding_map.shape[-1])

        total_instances = 0.
        lovasz_loss = 0.
        seediness_loss = 0.
        bandwidth_smoothness_loss = 0.

        torch_zero = torch.tensor(0).to(embedding_map).requires_grad_(False)

        for idx, (embeddings_per_seq, bandwidth_per_seq, seediness_per_seq, targets_per_seq) in \
                enumerate(zip(embedding_map, bandwidth_map, seediness_map, targets)):

            masks = targets_per_seq['masks']
            if masks.numel() == 0:
                continue

            ignore_masks = targets_per_seq['ignore_masks']

            assert masks.shape[-2:] == ignore_masks.shape[-2:], \
                "Masks tensor has shape {} while ignore mask has shape {}".format(masks.shape, ignore_masks.shape)

            assert masks.shape[-2:] == embedding_map.shape[2:4], \
                "Masks tensor has shape {} while embedding map has shape {}".format(masks.shape, embedding_map.shape)

            nonzero_mask_pts = masks.nonzero(as_tuple=False)
            if nonzero_mask_pts.shape[0] == 0:
                print("[ WARN] No valid mask points exist in sample.")
                continue

            _, instance_pt_counts = nonzero_mask_pts[:, 0].unique(sorted=True, return_counts=True)
            instance_id_sort_idx = nonzero_mask_pts[:, 0].argsort()
            nonzero_mask_pts = nonzero_mask_pts[instance_id_sort_idx]
            nonzero_mask_pts = nonzero_mask_pts.split(tuple(instance_pt_counts.tolist()))
            nonzero_mask_pts = tuple([nonzero_mask_pts[i].unbind(1)[1:] for i in range(len(nonzero_mask_pts))])

            instance_embeddings = [
                embeddings_per_seq[nonzero_mask_pts[n]]
                for n in range(len(nonzero_mask_pts))
            ]  # list(tensor[I, E])

            instance_bandwidths = [
                bandwidth_per_seq[nonzero_mask_pts[n]]
                for n in range(len(nonzero_mask_pts))
            ]  # list(tensor[I, E])

            instance_seediness = [
                seediness_per_seq[nonzero_mask_pts[n]]
                for n in range(len(nonzero_mask_pts))
            ]  # list(tensor[I, E])

            total_instances += len(nonzero_mask_pts)

            # regress seediness values for background to 0
            bg_mask_pts = (masks == 0).all(0).nonzero(as_tuple=False).unbind(1)
            bg_seediness_pts = seediness_per_seq[bg_mask_pts]
            bg_seediness_loss = F.mse_loss(bg_seediness_pts, torch.zeros_like(bg_seediness_pts), reduction='none')

            # ignore loss for ignore mask points
            ignore_mask_pts = ignore_masks[bg_mask_pts].unsqueeze(1)
            seediness_loss = seediness_loss + torch.where(ignore_mask_pts, torch_zero, bg_seediness_loss).mean()

            # compute bandwidth smoothness loss before applying activation
            bandwidth_smoothness_loss = bandwidth_smoothness_loss + self.compute_bandwidth_smoothness_loss(instance_bandwidths)

            # apply activation to bandwidths
            instance_bandwidths = [
                bandwidth_per_instance.exp() * 10.
                for bandwidth_per_instance in instance_bandwidths
            ]
            allprop=[];
            for n in range(len(nonzero_mask_pts)):  # iterate over instances
                probs_map = self.compute_prob_map(embeddings_per_seq, instance_embeddings[n], instance_bandwidths[n])
                logits_map = (probs_map * 2.) - 1.
                allprop.append(probs_map)
                instance_target = masks[n].flatten()
                if instance_target.sum(dtype=torch.long) == 0:
                    continue

                lovasz_loss = lovasz_loss + self.lovasz_hinge_loss(logits_map.flatten(), instance_target)
                instance_probs = probs_map.unsqueeze(3)[nonzero_mask_pts[n]].detach()
                seediness_loss = seediness_loss + F.mse_loss(instance_seediness[n], instance_probs, reduction='mean')

        if total_instances == 0:
            print("Process {}: Zero instances case occurred embedding loss".format(dist_utils.get_rank()))
            lovasz_loss = (bandwidth_map.sum() + embedding_map.sum()) * 0
            bandwidth_smoothness_loss = bandwidth_map.sum() * 0
            seediness_loss = seediness_map.sum() * 0
        else:
            # compute weighted sum of lovasz and variance losses based on number of instances per batch sample
            lovasz_loss = lovasz_loss / total_instances
            bandwidth_smoothness_loss = bandwidth_smoothness_loss / embedding_map.shape[0]  # divide by batch size
            seediness_loss = seediness_loss / float(total_instances + 1)
	
        now = str(datetime.datetime.now().time())[0:5]
        minute = int(now[3:5])
        

                       

        total_loss = (lovasz_loss * self.w_lovasz) + \
                     (bandwidth_smoothness_loss * self.w_variance_smoothness) + \
                     (seediness_loss * self.w_seediness)
        
        try:
          if minute%3==0:
              if exists(self.currentpath+str(minute)+'.tfg')==False: 
                  metric = self.clustermetric(instance_embeddings)
                      
                  lovas = lovasz_loss.mean().detach().cpu().numpy()
                  seed = seediness_loss.mean().detach().cpu().numpy()
                  total_loss = total_loss.detach().cpu().numpy()
                        
                  self.logger(minute,now,metric,lovas,seed,total_loss)
        except:
            pass
                             

        output_dict[ModelOutputConsts.OPTIMIZATION_LOSSES] = {
            LossConsts.EMBEDDING: total_loss * self.w
        }

        output_dict[ModelOutputConsts.OTHERS] = {
            LossConsts.LOVASZ_LOSS: lovasz_loss,
            LossConsts.VARIANCE_SMOOTHNESS: bandwidth_smoothness_loss,
        }

        output_dict[ModelOutputConsts.OTHERS][LossConsts.SEEDINESS_LOSS] = seediness_loss

    def compute_prob_map(self, embedding_map, instance_embeddings, instance_bandwidth):
        """
        Compute the fg/bg probability per instance
        :param embedding_map: tensor(T, H, W, E)
        :param instance_embeddings: tensor(N, E)
        :param instance_bandwidth: tensor(N, E - N_FREE_DIMS)
        :return: tensor(T, H, W)
        """
        embedding_center = instance_embeddings.mean(dim=0, keepdim=True)[None, None, :]
        mean_bandwidth = instance_bandwidth.mean(dim=0, keepdim=True)  # [1, E - N_FREE_DIMS]

        if self.n_free_dims > 0:
            mean_bandwidth = torch.cat((mean_bandwidth, self.free_dim_bandwidths), 1)

        mean_bandwidth = mean_bandwidth[None, None, :]

        probs = torch.exp(-0.5 * torch.sum(
            torch.pow(embedding_map - embedding_center, 2) * mean_bandwidth, dim=-1))

        return probs

    def compute_bandwidth_smoothness_loss(self, bandwidths):
        loss = 0.
        for bandwidths_per_instance in bandwidths:
            mean_bandwidth = bandwidths_per_instance.mean(dim=0, keepdim=True)
            loss += torch.pow(mean_bandwidth - bandwidths_per_instance, 2).mean()
        return loss / float(len(bandwidths))
