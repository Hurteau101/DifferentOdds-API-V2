import importlib

model = importlib.import_module('Books.SGP.fanduel_sgp')
my_class = getattr(model, 'FanduelSGP')
my_instance = my_class()
print(my_instance)
