import keras
import os
import shutil
from keras import layers
import matplotlib.pyplot as plt
import numpy as np

base_dir = "D:\迅雷下载\猫狗数据集\datasetcat_dog"
train_dir = os.path.join(base_dir, 'train')
train_dir_dog = os.path.join(train_dir, 'dog')
train_dir_cat = os.path.join(train_dir, 'cat')

test_dir = os.path.join(base_dir, 'test')
test_dir_dog = os.path.join(test_dir, 'dog')
test_dir_cat = os.path.join(test_dir, 'cat')

if not os.path.exists(base_dir):
    os.mkdir(base_dir)
    os.mkdir(train_dir)
    os.mkdir(train_dir_dog)
    os.mkdir(train_dir_cat)
    os.mkdir(test_dir)
    os.mkdir(test_dir_dog)
    os.mkdir(test_dir_cat)

    dc_dir = r"D:\迅雷下载\猫狗数据集\dc\train"

    # 将原本数据集的图片放入准备的数据集
    fnames = ['cat.{}.jpg'.format(i) for i in range(1000)]
    for fname in fnames:
        s = os.path.join(dc_dir, fname)
        d = os.path.join(train_dir_cat, fname)
        shutil.copyfile(s, d)

    fnames = ['cat.{}.jpg'.format(i) for i in range(1000, 1500)]
    for fname in fnames:
        s = os.path.join(dc_dir, fname)
        d = os.path.join(test_dir_cat, fname)
        shutil.copyfile(s, d)

    fnames = ['dog.{}.jpg'.format(i) for i in range(1000)]
    for fname in fnames:
        s = os.path.join(dc_dir, fname)
        d = os.path.join(train_dir_dog, fname)
        shutil.copyfile(s, d)

    fnames = ['dog.{}.jpg'.format(i) for i in range(1000, 1500)]
    for fname in fnames:
        s = os.path.join(dc_dir, fname)
        d = os.path.join(test_dir_dog, fname)
        shutil.copyfile(s, d)

from keras.preprocessing.image import ImageDataGenerator

train_datagen = ImageDataGenerator(rescale=1 / 255)  # rescale=1/255归一化
test_datagen = ImageDataGenerator(rescale=1 / 255)

train_generator = train_datagen.flow_from_directory(train_dir, target_size=(200, 200), batch_size=20,
                                                    class_mode='binary')
test_generator = train_datagen.flow_from_directory(test_dir, target_size=(200, 200), batch_size=20, class_mode='binary')

model = keras.Sequential()

model.add(layers.Conv2D(64, (3 * 3), activation="relu", input_shape=(200, 200, 3)))
model.add(layers.Conv2D(64, (3 * 3), activation="relu"))
model.add(layers.MaxPooling2D())
model.add(layers.Dropout(0.25))  # Dropout层防止过拟合
model.add(layers.Conv2D(64, (3 * 3), activation="relu"))
model.add(layers.Conv2D(64, (3 * 3), activation="relu"))
model.add(layers.MaxPooling2D())
model.add(layers.Dropout(0.25))
model.add(layers.Conv2D(64, (3 * 3), activation="relu"))
model.add(layers.Conv2D(64, (3 * 3), activation="relu"))
model.add(layers.MaxPooling2D())
model.add(layers.Dropout(0.25))

model.add(layers.Flatten())
model.add(layers.Dense(256, activation='relu'))
model.add(layers.Dropout(0.5))
model.add(layers.Dense(1, activation='sigmoid'))

model.compile(optimizer='adam', loss='binary_crossentropy', metrics=['acc'])

history = model.fit_generator(train_generator, epochs=30, steps_per_epoch=100, validation_data=test_generator,
                              validation_steps=50)  # steps_per_epoch训练多少步是一个epoch


