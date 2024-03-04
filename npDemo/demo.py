import numpy as np

# dt = np.dtype([('age',np.int8)])
# a = np.array([(10,),(20,),(30,)], dtype = dt)
#
# x = np.zeros(3, dtype =  [('x',  'i4'),  ('y',  'i4')])
# # x = np.empty([3,2], dtype =  int)
# print(a)
# a = np.arange(8).reshape(2,4)
# print(a.flatten())
#
# x = np.array([[1], [2], [3]])
# y = np.array([4, 5, 6])
#
# b = np.broadcast(x,y)
# print(b)

a = np.arange(4).reshape(2, 2)
'原数组：'

'调用 broadcast_to 函数之后：'

# b=np.broadcast_to(a, (1, 4))
print(a)
a = np.array([5,2,6,2,7,5,6,8,2,9])
u = np.unique(a)
print(u)