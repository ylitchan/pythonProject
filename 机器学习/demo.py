from tensorflow import keras
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd #pandas是很好用的数据预处理工具
from keras import layers
from keras.utils import to_categorical

data=pd.read_excel("D:\迅雷下载\我的模板_全部A股区间(非ST).xlsx")
def regularit(df):
    newDataFrame = pd.DataFrame(index=df.index)
    columns = df.columns.tolist()
    for c in columns:
        d = df[c]
        MAX = d.max()
        MIN = d.min()
        newDataFrame[c] = ((d - MIN) / (MAX - MIN)).tolist()
    return newDataFrame
data=regularit(data)
# print(data)
#这是excel文件，注意WPS编辑下，可能会导致错误发生，最好使用office，没办法就在WPS保存中选择csv格式，不要直接修改后缀名
ydata=data.iloc[:, -1]
print(ydata)
# ydata=np.array(ydata)
# ydata = to_categorical(ydata,4)
# print(ydata)
xdata=data.iloc[:, :-1]
print(xdata,'这是xdata')
model = keras.Sequential()
model.add(layers.Dense(224,input_dim=7,activation='sigmoid'))
model.add(layers.Dense(7,activation='sigmoid'))
model.add(layers.Dense(1,activation='sigmoid'))
# model.add(layers.Dense(1))
model.summary()
model.compile(optimizer='adam',loss='binary_crossentropy',metrics=['acc'])
history=model.fit(xdata,ydata,epochs=300)
plt.plot(range(300),history.history.get('acc'))
plt.show()
history.history.get('loss')
print(model.predict(xdata[:10]))
# xdata=xdata.apply(lambda x: (x - np.min(x)) / (np.max(x) - np.min(x)))
# xdata=np.array(xdata).reshape(4857,5,5)
# # z=xdata.head()
# # print(xdata)#打印前几行
# # x=data[data.columns[:,:24]]#取前三列为x数组
# # print(x.shape,type(x),x[1])
# # y=data.iloc[:,-1]#取最后一列为y数组
# xdata=np.expand_dims(xdata,axis=-1)
# print(xdata.shape)
# # ydata=ydata.astype(int)
# print(ydata.shape)
# # model= keras.Sequential()
# # model.add(layers.Dense(1,input_dim=3))#输出1维度，输入维度为3 y_pred=w1*x1+w2*x2+w3*x3+b
# # model.summary()
# #
# # model.compile(optimizer='adam',loss='mse')#msejunfangc
# # model.fit(x,y,epochs=5000)
# #
# #
# # w=model.predict(pd.DataFrame([[300,68,60]]))
# # print(w)
# model=keras.Sequential()
# model.add(layers.Conv2D(64,(1,5),activation='tanh',input_shape=(5,5,1)))
# # model.add(layers.Conv2D(64,(3,3),activation='relu'))
# # model.add(layers.MaxPooling2D())
# # model.add(layers.Conv2D(64,(3,3),activation='relu',input_shape=(28,28,1)))
# # model.add(layers.Conv2D(64,(3,3),activation='relu'))
# # model.add(layers.MaxPooling2D())
# model.add(layers.Flatten())
# model.add(layers.Dense(512,activation='tanh'))
# model.add(layers.Dense(256,activation='tanh'))
# model.add(layers.Dense(128,activation='tanh'))
# model.add(layers.Dense(64,activation='tanh'))
# model.add(layers.Dense(32,activation='tanh'))
# # model.add(layers.Dropout(0.5))
# model.add(layers.Dense(4,activation='softmax'))
# model.summary()
# model.compile(optimizer='adam',loss='sparse_categorical_crossentropy',metrics=['acc'])
# model.fit(xdata,ydata,epochs=1000,batch_size=4857)#,validation_data=(test_image,test_label))
# # y=np.argmax(model.predict(test_image[:10]),axis=1)#测试测试集的前十张，输出1-10，十个数的可能概率
# # print(y)
# # print(test_label[:10])#打印测试集的前十个原来的标签
# #
# #
