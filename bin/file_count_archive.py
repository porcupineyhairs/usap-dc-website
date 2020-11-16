#!/opt/rh/python27/root/usr/bin/python

"""
file_count_archive.py

@author: fnitsche & nshane
This version to be run in /archive/usap-dc/dataset with
> python file_count_archive <dir_name>
Will return values to be entered manually in DB
"""

import os
import sys
import tarfile
import gzip
import zipfile
import mimetypes


# get uncompressed file size of gzipped file
def get_uncompressed_size(file):
    fileobj = open(file, 'r')
    fileobj.seek(-8, 2)
    crc32 = gzip.read32(fileobj)
    isize = gzip.read32(fileobj)  # may exceed 2GB
    fileobj.close()
    return isize


def usap_get_url_list_test():
    data_list = []
    (conn, cur) = connect_to_db()
    cur.execute("SELECT id, url FROM dataset where url IS NOT NULL;")
    data = cur.fetchall()

    print('records: ', len(data))
    for row in list(data):
        data_list.append(row)
        # print(row)
    # print(data)
    
    cur.close()
    conn.close()

    return data_list


def get_dir_info(topdir):
    # print()
    # print(topdir)
    file_count = 0
    subdir_count = -1  # because root is counted as one as well
    file_size = 0
    u_file_size = 0
    mime_types = set()
    for root, dirs, files in os.walk(topdir):
        subdir_count += 1
        for name in files:
            # print(name)
            path_name = os.path.join(root, name)
            if '.tar' in name:
                # print(path_name)
                try:
                    with tarfile.open(path_name) as archive:
                        count = 0
                        for member in archive:
                            if member.isreg():
                                count += 1
                                mime_types.add(mimetypes.guess_type(member.name)[0])
                        # count = sum(1 for member in archive if member.isreg())
                        file_count += count
                except Exception as e:
                    print("Couldn't open tar file %s\n" %name)
                    print(str(e))
                    file_count += 1
            else:
                file_count += 1
                mime_types.add(mimetypes.guess_type(name)[0])
            
            this_file_size = os.path.getsize(os.path.join(root, name))
            file_size += this_file_size

            # if file is zipped, get  the uncompressed file size too
            if '.gz' in name :
                u_file_size += get_uncompressed_size(path_name)
            elif '.zip' in name:
                zp = zipfile.ZipFile(path_name)
                u_file_size += sum(zinfo.file_size for zinfo in  zp.filelist)
            else:
                u_file_size += this_file_size    

    mime_types.discard(None) 
    # print("-> subdirs = ", subdir_count)
    print("-> file_count = ", file_count)
    print("-> file_size_on_disk = ", file_size)
    print("-> file_size_uncompressed: ", u_file_size)
    print("-> mime_types: ", lst2pgarr(list(mime_types)))
   
    # return file_count, file_size, u_file_size, list(mime_types)


def lst2pgarr(alist):
    if len(alist) == 0:
        return None
    return '{' + ','.join(alist) + '}'

    
    
# main
dir_name = sys.argv[1]
get_dir_info(dir_name)
