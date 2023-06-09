from tensorflow.keras import layers
from tensorflow import keras
from keras.models import load_model
import models
import DeformableConvLayerKeras as DCL
from models.Spectral import run


def network(args):
  if args.network=='inception_default':
    return inception_default(args.imagesize,args.num_class,args.channel_input)
  if args.network=='inception_deform':
    return inception_deform_light(args.imagesize,args.num_class,args.channel_input,args.batchsize)
  if args.network=='inception_mobilenet':
    return inception_mobilenet(args.imagesize,args.num_class)
  if args.network=='mobilenet_s1':
    return mobilenet_s1(args.imagesize,args.num_class)
  if args.network=='ins_bin_tune':
    return ins_bin_tune(args.imagesize,args.num_class)
  if args.network=='spectral':
    return run.start(args)
def inception_default(img_size, num_classes,channel_input):
    inputs = keras.Input(shape=img_size + (channel_input,))

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
  
def inception_deform_light(img_size, num_classes,channel_input,batch_size):
    inputs = keras.Input(shape=img_size + (channel_input,))

    ### [First half of the network: downsampling inputs] ###

    # Entry block
    x = DCL.DeformableConv2D(batch_size = batch_size,
                                filters = 32,
                                kernel_size = (3,3),
                                name = 'layer1',
                                kernel_initializer='glorot_uniform',strides=2, padding="same")(inputs)
    x = layers.MaxPooling2D(3, strides=2, padding="same")(x)
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
    x = DCL.DeformableConv2D(batch_size = batch_size,
                            filters = 32,
                            kernel_size = (3,3),
                            name = 'layer2',
                            kernel_initializer='glorot_uniform',strides=2, padding="same")(x)
      
    outputs = layers.Conv2D(num_classes, 3, activation="softmax", padding="same")(x)

    # Define the model
    model = keras.Model(inputs, outputs)
    return model
  
def inception_deform(img_size, num_classes,channel_input,batch_size):  
  inputs = keras.Input(shape=img_size + (channel_input,))

  ### [First half of the network: downsampling inputs] ###

  # Entry block
  #x = layers.Conv2D(32, 3, strides=2, padding="same")(inputs)
  x = DCL.DeformableConv2D(batch_size = batch_size,
                                filters = 32,
                                kernel_size = (3,3),
                                name = 'layer1',
                                kernel_initializer='glorot_uniform',strides=2, padding="same")(inputs)
  x = layers.MaxPooling2D(3, strides=2, padding="same")(x)
  x = layers.BatchNormalization()(x)
  x = layers.Activation("relu")(x)

  previous_block_activation = x  # Set aside residual

  # Blocks 1, 2, 3 are identical apart from the feature depth.
  p=0;
  for filters in [64, 128, 256]:
      p+=5;
      x = layers.Activation("relu")(x)
      x = DCL.DeformableConv2D(batch_size = batch_size,
                                filters = filters,
                                kernel_size = (3,3),
                                name = 'layer'+str(p),
                                kernel_initializer='glorot_uniform', padding="same")(x)
      x = layers.BatchNormalization()(x)

      x = layers.Activation("relu")(x)
      x = DCL.DeformableConv2D(batch_size = batch_size,
                                filters = filters,
                                kernel_size = (3,3),
                                name = 'layer'+str(p+1),
                                kernel_initializer='glorot_uniform', padding="same")(x)
      x = layers.BatchNormalization()(x)
      x = layers.MaxPooling2D(3, strides=2, padding="same")(x)

      # Project residual
      residual = DCL.DeformableConv2D(batch_size = batch_size,
                                filters = filters,
                                kernel_size = (3,3),
                                kernel_initializer='glorot_uniform',name = 'layer'+str(p+2), padding="same")(previous_block_activation)
      residual = layers.MaxPooling2D(3, strides=2, padding="same")(residual)

      x = layers.add([x, residual])  # Add back residual
      previous_block_activation = x  # Set aside next residual

      ### [Second half of the network: upsampling inputs] ###

  for filters in [256, 128, 64, 32]:
    p+=5
    x = layers.Activation("relu")(x)
    x = DCL.DeformableConv2D(batch_size = batch_size,
                              filters = filters,
                              kernel_size = (3,3),
                              name = 'layer'+str(p+1),
                              kernel_initializer='glorot_uniform', padding="same")(x)
    x = layers.BatchNormalization()(x)

    x = layers.Activation("relu")(x)
    x = DCL.DeformableConv2D(batch_size = batch_size,
                              filters = filters,
                              kernel_size = (3,3),
                              name = 'layer'+str(p+2),
                              kernel_initializer='glorot_uniform', padding="same")(x)
    x = layers.BatchNormalization()(x)

    x = layers.UpSampling2D(2)(x)

    # Project residual
    residual = layers.UpSampling2D(2)(previous_block_activation)
    #residual = layers.Conv2D(filters, 1, padding="same")(residual)
    residual = DCL.DeformableConv2D(batch_size = batch_size,
                              filters = filters,
                              kernel_size = (3,3),
                              name = 'layer'+str(p+3),
                              kernel_initializer='glorot_uniform', padding="same")(residual)

    x = layers.add([x, residual])  # Add back residual
    previous_block_activation = x  # Set aside next residual

      # Add a per-pixel classification layer
  outputs = DCL.DeformableConv2D(batch_size = batch_size,
                            filters = num_classes,
                            kernel_size = (3,3),
                            name = 'layer'+str(p+4),
                            kernel_initializer='glorot_uniform', padding="same")(x)


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
    outputs = layers.Conv2D(num_classes, 3, activation="softmax", padding="same")(x)

    # Define the model
    model = keras.Model(inputs, outputs)
    return model
  
def ins_bin_tune(img_size, num_classes):
  model = load_model('inception_default_2x_binary_c41.h5')
  layer_name = 'add_6'
  x = model.get_layer(layer_name).output
  outputs = layers.Conv2D(num_classes, 3, activation="softmax", padding="same",name='last_conv')(x)
  model_new= keras.Model(inputs=model.input, outputs=outputs);
  
  return model_new

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

