from tensorflow.keras import layers
from tensorflow import keras
from deformable_conv_layer import DeformableConvLayer
import tensorflow as tf

def network(args):
  if args.network=='inception_3d_default':
    return inception_3d_default(args.imagesize,2,args.subseq_length)
  if args.network=='inception_mobilenet':
    return inception_mobilenet(args.imagesize,2)
  if args.network=='mobilenet_s1':
    return mobilenet_s1(args.imagesize,2)
  
def inception_3d_default(img_size, num_classes,subseq_length):
  inputs = keras.Input(shape=img_size + (3*subseq_length,1))

  x = tf.keras.layers.Conv3D(32, 3,strides=(2, 2, 1),padding='same')(inputs)
  x = layers.BatchNormalization()(x)
  x = layers.Activation("relu")(x)

  previous_block_activation = x  # Set aside residual

  # Blocks 1, 2, 3 are identical apart from the feature depth.
  for filters in [64, 128, 256]:
      x = layers.Activation("relu")(x)
      x = layers.Conv3D(filters, 3, padding="same")(x)
      x = layers.BatchNormalization()(x)

      x = layers.Activation("relu")(x)
      x = layers.Conv3D(filters, 3, padding="same")(x)
      x = layers.BatchNormalization()(x)
      if filters==64:
        strd=(2,2,3);
      else:
        strd=(2,2,1);
      x = layers.MaxPooling3D(3, strides=strd, padding="same")(x)

      # Project residual
      residual = layers.Conv3D(filters, 1, strides=strd, padding="same")(
          previous_block_activation
      )
      x = layers.add([x, residual])  # Add back residual
      previous_block_activation = x  # Set aside next residual

  for filters in [256, 128, 64, 32]:
      x = layers.Activation("relu")(x)
      x = layers.Conv3DTranspose(filters, 3, padding="same")(x)
      x = layers.BatchNormalization()(x)
      x = layers.Activation("relu")(x)
      x = layers.Conv3DTranspose(filters, 3, padding="same")(x)
      x = layers.BatchNormalization()(x)

      x = layers.UpSampling3D((2,2,1))(x)

      # Project residual
      residual = layers.UpSampling3D((2,2,1))(previous_block_activation)
      residual = layers.Conv3D(filters, 1, padding="same")(residual)
      x = layers.add([x, residual])  # Add back residual
      previous_block_activation = x  # Set aside next residual


  # Add a per-pixel classification layer
  y = layers.Conv3D(num_classes, 3, activation="softmax", padding="same")(x)
  outputs = layers.Reshape((y.shape[1],y.shape[2],y.shape[3]*y.shape[4]))(y)
  if subseq_length==6:
    o1,o2,o3,o4,o5,o6 = tf.split(outputs, num_or_size_splits=subseq_length, axis=-1)
    model = keras.Model(inputs,[o1,o2,o3,o4,o5,o6])
  elif subseq_length==4:
    o1,o2,o3,o4 = tf.split(outputs, num_or_size_splits=subseq_length, axis=-1)
    model = keras.Model(inputs,[o1,o2,o3,o4])

  return model

def inception_default(img_size, num_classes):
    inputs = keras.Input(shape=img_size + (3,))

    ### [First half of the network: downsampling inputs] ###

    # Entry block
    x = layers.Conv2D(32, 3, strides=2, padding="same")(inputs)
    x = layers.BatchNormalization()(x)
    x = layers.Activation("relu")(x)

    previous_block_activation = x  # Set aside residual

    # Blocks 1, 2, 3 are identical apart from the feature depth.
    for filters in [64, 128, 256]:
        x = layers.Activation("relu")(x)
        x = layers.SeparableConv2D(filters, 3, padding="same")(x)
        x = layers.BatchNormalization()(x)

        x = layers.Activation("relu")(x)
        x = layers.SeparableConv2D(filters, 3, padding="same")(x)
        x = layers.BatchNormalization()(x)

        x = layers.MaxPooling2D(3, strides=2, padding="same")(x)

        # Project residual
        residual = layers.Conv2D(filters, 1, strides=2, padding="same")(
            previous_block_activation
        )
        x = layers.add([x, residual])  # Add back residual
        previous_block_activation = x  # Set aside next residual

    ### [Second half of the network: upsampling inputs] ###

    for filters in [256, 128, 64, 32]:
        x = layers.Activation("relu")(x)
        x = layers.Conv2DTranspose(filters, 3, padding="same")(x)
        x = layers.BatchNormalization()(x)

        x = layers.Activation("relu")(x)
        x = layers.Conv2DTranspose(filters, 3, padding="same")(x)
        x = layers.BatchNormalization()(x)

        x = layers.UpSampling2D(2)(x)

        # Project residual
        residual = layers.UpSampling2D(2)(previous_block_activation)
        residual = layers.Conv2D(filters, 1, padding="same")(residual)
        x = layers.add([x, residual])  # Add back residual
        previous_block_activation = x  # Set aside next residual

    # Add a per-pixel classification layer
    outputs = layers.Conv2D(num_classes, 3, activation="softmax", padding="same")(x)

    # Define the model
    model = keras.Model(inputs, outputs)
    return model

def inception_mobilenet(img_size, num_classes):
    inputs = keras.Input(shape=img_size + (3,))
    ### [First half of the network: downsampling inputs] ###

    # Entry block
    x = layers.Conv2D(32, 3, strides=2, padding="same")(inputs)
    x = layers.BatchNormalization()(x)
    x = layers.Activation("relu")(x)

    previous_block_activation = x  # Set aside residual

    # Blocks 1, 2, 3 are identical apart from the feature depth.
    for filters in [64, 128, 256]:
        x = layers.Activation("relu")(x)
        x = layers.SeparableConv2D(filters, 3, padding="same")(x)
        x = layers.BatchNormalization()(x)

        x = layers.Activation("relu")(x)
        x = layers.SeparableConv2D(filters, 3, padding="same")(x)
        x = layers.BatchNormalization()(x)

        x = layers.MaxPooling2D(3, strides=2, padding="same")(x)

        # Project residual
        residual = layers.Conv2D(filters, 1, strides=2, padding="same")(
            previous_block_activation
        )
        x = layers.add([x, residual])  # Add back residual
        previous_block_activation = x  # Set aside next residual

    ### [Second half of the network: upsampling inputs] ###

    backbone = keras.applications.MobileNetV2(
        weights="imagenet", include_top=False, input_shape=img_size + (3,)
    )
    backbone.trainable = False
    z = keras.applications.mobilenet_v2.preprocess_input(inputs)
    z = backbone(z)
    z = layers.SeparableConv2D(480, 3, strides=1, padding="valid")(z)
    z = layers.Reshape((24,40,90))(z)

    x = layers.Concatenate(axis=-1)([x, z])

    for filters in [256, 128, 64, 32]:
        x = layers.Activation("relu")(x)
        x = layers.Conv2DTranspose(filters, 3, padding="same")(x)
        x = layers.BatchNormalization()(x)

        x = layers.Activation("relu")(x)
        x = layers.Conv2DTranspose(filters, 3, padding="same")(x)
        x = layers.BatchNormalization()(x)

        x = layers.UpSampling2D(2)(x)

        # Project residual
        residual = layers.UpSampling2D(2)(previous_block_activation)
        residual = layers.Conv2D(filters, 1, padding="same")(residual)
        x = layers.add([x, residual])  # Add back residual
        previous_block_activation = x  # Set aside next residual

    # Add a per-pixel classification layer
    outputs = layers.Conv2D(2, 3, activation="softmax", padding="same")(x)

    # Define the model
    model = keras.Model(inputs, outputs)
    return model
def mobilenet_s1(img_size, num_classes):
  
    inputs = keras.Input(shape=img_size + (3,))
    backbone = keras.applications.MobileNetV2(
        weights="imagenet", include_top=False, input_shape=img_size + (3,)
    )
    backbone.trainable = False
    
    x = keras.applications.mobilenet_v2.preprocess_input(inputs)
    x = backbone(x)
    x = layers.SeparableConv2D(640, 3, strides=1, padding="valid")(x)
    x = layers.BatchNormalization()(x)
    x = layers.Activation("relu")(x)
    x = layers.Reshape((48,80,30))(x)
    x = layers.UpSampling2D(2)(x)
    x = layers.SeparableConv2D(32, 3, strides=1, padding="same")(x)
    x = layers.BatchNormalization()(x)
    x = layers.Activation("relu")(x)

    x = layers.UpSampling2D(2)(x)
    x = layers.SeparableConv2D(16, 3, strides=1, padding="same")(x)
    x = layers.BatchNormalization()(x)
    x = layers.Activation("relu")(x)

    x = layers.UpSampling2D(2)(x)
    x = layers.SeparableConv2D(8, 3, strides=1, padding="same")(x)
    x = layers.BatchNormalization()(x)
    x = layers.Activation("relu")(x)

    outputs = layers.Conv2D(num_classes, 3, activation="softmax", padding="same")(x)

    model = keras.Model(inputs, outputs)
    return model

