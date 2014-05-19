import urllib


def http_request(ip_address, command, post_params=None):
    # post_params must be a dictionay
    if post_params:
        params = urllib.urlencode(post_params)
        f = urllib.urlopen('http://' + ip_address + command, params)
    else:
        f = urllib.urlopen('http://' + ip_address + command)

    print('message sent, reply follows:')
    print(f.read())


def list_integers_string(string_list):
    """
    Accepts comma separated string list of integers
    """
    integers_list = string_list.split(',')
    integers_list = map(int, integers_list)
    return integers_list


def frame_percentage(item):
    if item.frame_start == item.current_frame:
            return 0
    else:
        frame_count = item.frame_end - item.frame_start + 1
        current_frame = item.current_frame - item.frame_start + 1
        percentage_done = 100 / frame_count * current_frame
        return percentage_done


# def create_tables():
#     """
#     Create the required databases during installation.

#     Based on the classes specified above. This function is embedded in
#     the install_brender function.
#     """
#     Workers.create_table()
#     Shows.create_table()
#     Shots.create_table()
#     Jobs.create_table()
#     Settings.create_table()


# def add_random_workers(workers_amount):
#     """
#     Create the specified amount of workers.

#     Assigns some random values as hostname and mac_address. Used only
#     for testing purposes.
#     TODO: make sure that all the properties of a worker are added here
#     """
#     for i in range(workers_amount):
#         Workers.create(mac_address=123 + i,
#                        hostname='worker_' + str(i),
#                        status='enabled',
#                        ip_address='192.168.1.' + str(i),
#                        connection='offline',
#                        warning=False,
#                        config='JSON string')
#     print("Database filled with " + str(workers_amount) + " workers.")


# def create_database():
#     """
#     Checks if the database exists

#     We check for the existence of the file on disc. If the file is not
#     found we create one and we populate it with the brender schema from
#     this file.

#     """
#     try:
#         with open(DATABASE):
#             # connect to database found in DATABASE
#             db.init(DATABASE)
#     except IOError:
#         print('[Info] Creating brender.sqlite database')
#         open(DATABASE, 'a').close()
#         # before creating tables we should connect to it
#         db.init(DATABASE)
#         create_tables()
#         print('[Info] Database created')

