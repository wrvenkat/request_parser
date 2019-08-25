from request_parser.utils.datastructures import MultiValueDict

multiValDict = MultiValueDict({'name': ['Adrian', 'Simon'], 'position': ['Developer']})
print(multiValDict['name'])
print(multiValDict.get('asdasdaswbasf', 'position'))
print(multiValDict.get('name'))
print(multiValDict.getlist('name'))
print(multiValDict.getlist('position'))
print(multiValDict.lists())
print(list(multiValDict.values()))
print(list(multiValDict.items()))
print(multiValDict.dict())

#checking setlist
multiValDict.setlist('name','modified')
print(multiValDict)
print(multiValDict['name'])
#checking setlist
multiValDict.setlist('name',['modified_list_item1','modified_list_item2'])
print(multiValDict)
print(multiValDict['name'])
#checking setlist
multiValDict.setlist('name',['modified_list_item1'])
print(multiValDict)
print(multiValDict['name'])

#setdefault check
multiValDict.setdefault('new_key_1','default_name')
print(multiValDict['new_key_1'])

#setdefaultlist check
multiValDict.setlistdefault('new_key_2',['default_name1','default_name2'])
print(multiValDict['new_key_2'])

#update() test
multiValDict2 = MultiValueDict({'name1': ['name1', 'name2'],'position2':['mason']})
#this one errors out saying more than 1 arg received
#multiValDict.update('asdasd', 'bhjvkhj')
#this one errors out "AttributeError: 'str' object has no attribute 'items'"
#multiValDict.update('asdasd123123')
#this one succeeds!
#multiValDict.update(multiValDict2)
#the following one succeeds but should be noted that ['name1', 'name2'] and ['mason']
#are all converted into another list i.e [['name1', 'name2']] and [['mason']]
multiValDict.update({'name1': ['name1', 'name2'],'position2':['mason']})
print(multiValDict)