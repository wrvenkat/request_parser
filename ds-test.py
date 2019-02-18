from utils.datastructures import MultiValueDict

multiValDict = MultiValueDict({'name': ['Adrian', 'Simon'], 'position': ['Developer']})
print multiValDict['name']
print multiValDict.get('asdasdaswbasf', 'position')
print multiValDict.get('name')
print multiValDict.getlist('name')
print multiValDict.getlist('position')
print multiValDict.lists()
print multiValDict.values()
print multiValDict.items()
print multiValDict.dict()

#checking setlist
multiValDict.setlist('name','modified')
print multiValDict
print multiValDict['name']
#checking setlist
multiValDict.setlist('name',['modified_list_item1','modified_list_item2'])
print multiValDict
print multiValDict['name']
#checking setlist
multiValDict.setlist('name',['modified_list_item1'])
print multiValDict
print multiValDict['name']

#setdefault check
multiValDict.setdefault('new_key_1','default_name')
print multiValDict['new_key_1']

#setdefaultlist check
multiValDict.setlistdefault('new_key_2',['default_name1','default_name2'])
print multiValDict['new_key_2']