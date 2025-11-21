def add(a,b):
    return a+b
def abs(x):
    if x>=0:
        return x
    else:
        return -x
    

class Person:
    def __init__(self):
        self.name = "张三"
        self.age = 20   
    def info(self):
        return f"姓名：{self.name}，年龄：{self.age}"