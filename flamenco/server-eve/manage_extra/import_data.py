def import_data(path):
    import json
    import pprint
    from bson import json_util
    if not os.path.isfile(path):
        return "File does not exist"
    with open(path, 'r') as infile:
        d = json.load(infile)

    def commit_object(collection, f, parent=None):
        variation_id = f.get('variation_id')
        if variation_id:
            del f['variation_id']

        asset_id = f.get('asset_id')
        if asset_id:
            del f['asset_id']

        node_id = f.get('node_id')
        if node_id:
            del f['node_id']

        if parent:
            f['parent'] = parent
        else:
            if f.get('parent'):
                del f['parent']

        #r = [{'_status': 'OK', '_id': 'DRY-ID'}]
        r = post_item(collection, f)
        if r[0]['_status'] == 'ERR':
            print r[0]['_issues']
            print "Tried to commit the following object"
            pprint.pprint(f)

        # Assign the Mongo ObjectID
        f['_id'] = str(r[0]['_id'])
        # Restore variation_id
        if variation_id:
            f['variation_id'] = variation_id
        if asset_id:
            f['asset_id'] = asset_id
        if node_id:
            f['node_id'] = node_id
        try:
            print "{0} {1}".format(f['_id'], f['name'])
        except UnicodeEncodeError:
            print "{0}".format(f['_id'])
        return f

    # Build list of parent files
    parent_files = [f for f in d['files'] if 'parent_asset_id' in f]
    children_files = [f for f in d['files'] if 'parent_asset_id' not in f]

    for p in parent_files:
        # Store temp property
        parent_asset_id = p['parent_asset_id']
        # Remove from dict to prevent invalid submission
        del p['parent_asset_id']
        # Commit to database
        p = commit_object('files', p)
        # Restore temp property
        p['parent_asset_id'] = parent_asset_id
        # Find children of the current file
        children = [c for c in children_files if c['parent'] == p['variation_id']]
        for c in children:
            # Commit to database with parent id
            c = commit_object('files', c, p['_id'])


    # Merge the dicts and replace the original one
    d['files'] = parent_files + children_files

    # Files for picture previews of folders (groups)
    for f in d['files_group']:
        item_id = f['item_id']
        del f['item_id']
        f = commit_object('files', f)
        f['item_id'] = item_id

    # Files for picture previews of assets
    for f in d['files_asset']:
        item_id = f['item_id']
        del f['item_id']
        f = commit_object('files',f)
        f['item_id'] = item_id


    nodes_asset = [n for n in d['nodes'] if 'asset_id' in n]
    nodes_group = [n for n in d['nodes'] if 'node_id' in n]

    def get_parent(node_id):
        #print "Searching for {0}".format(node_id)
        try:
            parent = [p for p in nodes_group if p['node_id'] == node_id][0]
        except IndexError:
            return None
        return parent

    def traverse_nodes(parent_id):
        parents_list = []
        while True:
            parent = get_parent(parent_id)
            #print parent
            if not parent:
                break
            else:
                parents_list.append(parent['node_id'])
                if parent.get('parent'):
                    parent_id = parent['parent']
                else:
                    break
        parents_list.reverse()
        return parents_list

    for n in nodes_asset:
        node_type_asset = db.node_types.find_one({"name": "asset"})
        if n.get('picture'):
            filename = os.path.splitext(n['picture'])[0]
            pictures = [p for p in d['files_asset'] if p['name'] == filename]
            if pictures:
                n['picture'] = pictures[0]['_id']
                print "Adding picture link {0}".format(n['picture'])
        n['node_type'] = node_type_asset['_id']
        # An asset node must have a parent
        # parent = [p for p in nodes_group if p['node_id'] == n['parent']][0]
        parents_list = traverse_nodes(n['parent'])

        tree_index = 0
        for node_id in parents_list:
            node = [p for p in nodes_group if p['node_id'] == node_id][0]

            if node.get('_id') is None:
                node_type_group = db.node_types.find_one({"name": "group"})
                node['node_type'] = node_type_group['_id']
                # Assign picture to the node group
                if node.get('picture'):
                    filename = os.path.splitext(node['picture'])[0]
                    picture = [p for p in d['files_group'] if p['name'] == filename][0]
                    node['picture'] = picture['_id']
                    print "Adding picture link to node {0}".format(node['picture'])
                if tree_index == 0:
                    # We are at the root of the tree (so we link to the project)
                    node_type_project = db.node_types.find_one({"name": "project"})
                    node['node_type'] = node_type_project['_id']
                    parent = None
                    if node['properties'].get('picture_square'):
                        filename = os.path.splitext(node['properties']['picture_square'])[0]
                        picture = [p for p in d['files_group'] if p['name'] == filename][0]
                        node['properties']['picture_square'] = picture['_id']
                        print "Adding picture_square link to node"
                    if node['properties'].get('picture_header'):
                        filename = os.path.splitext(node['properties']['picture_header'])[0]
                        picture = [p for p in d['files_group'] if p['name'] == filename][0]
                        node['properties']['picture_header'] = picture['_id']
                        print "Adding picture_header link to node"
                else:
                    # Get the parent node id
                    parents_list_node_id = parents_list[tree_index - 1]
                    parent_node = [p for p in nodes_group if p['node_id'] == parents_list_node_id][0]
                    parent = parent_node['_id']
                print "About to commit Node"
                commit_object('nodes', node, parent)
            tree_index += 1
        # Commit the asset
        print "About to commit Asset {0}".format(n['asset_id'])
        parent_node = [p for p in nodes_group if p['node_id'] == parents_list[-1]][0]
        try:
            asset_file = [a for a in d['files'] if a['md5'] == n['properties']['file']][0]
            n['properties']['file'] = str(asset_file['_id'])
            commit_object('nodes', n, parent_node['_id'])
        except IndexError:
            pass

    return


    # New path with _
    path = '_' + path
    with open(path, 'w') as outfile:
        json.dump(d, outfile, default=json_util.default)
    return
