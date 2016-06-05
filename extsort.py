#!/usr/bin/env python

#
# Sort large text files in a minimum amount of memory
#
import bz2
import os
import argparse


def main():
    """
    Program entry point.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('-m',
                        '--mem',
                        help='amount of memory to use for sorting',
                        default='100M')
    parser.add_argument('filename',
                        metavar='<filename>',
                        nargs=1,
                        help='name of file to sort')
    args = parser.parse_args()

    sorter = ExternalSort(parse_memory(args.mem))
    sorter.sort(args.filename[0])


def parse_memory(string):
    """
    Parses memory usage argument string.
    """
    if string[-1].lower() == 'k':
        return int(string[:-1]) * 1024
    elif string[-1].lower() == 'm':
        return int(string[:-1]) * 1024 * 1024
    elif string[-1].lower() == 'g':
        return int(string[:-1]) * 1024 * 1024 * 1024
    else:
        return int(string)


class ExternalSort(object):
    """
    Class for external sorting.
    Splits files in blocks to small files, sorts and merges to output file.
    """

    def __init__(self, block_size):
        self.block_size = block_size

    def sort(self, filename, sort_key=None):
        # Get number of block files.
        num_blocks = self.get_number_blocks(filename, self.block_size)
        splitter = BZ2FileSplitter(filename)
        splitter.split(self.block_size, sort_key)

        merger = BZ2FileMerger(NWayMerge())
        buffer_size = self.block_size / (num_blocks + 1)
        merger.merge(splitter.get_block_filenames(), 'out_' + filename, buffer_size)

        splitter.cleanup()

    def get_number_blocks(self, filename, block_size):
        return (os.stat(filename).st_size / block_size) + 1


class FileSplitter(object):
    """
    Splits file in blocks.
    """
    BLOCK_FILENAME_FORMAT = 'block_{0}.dat'

    def __init__(self, filename):
        self.filename = filename
        self.block_filenames = []

    def write_block(self, data, block_number):
        filename = self.BLOCK_FILENAME_FORMAT.format(block_number)
        # file = self.get_file_obj(filename, 'w')
        file = open(filename, 'w')
        file.write(data)
        file.close()
        self.block_filenames.append(filename)

    def get_block_filenames(self):
        return self.block_filenames

    def get_file_obj(self, filename, mode):
        return open(filename, mode)

    def split(self, block_size, sort_key=None):
        file = self.get_file_obj(self.filename, 'r')
        i = 0

        while True:
            lines = file.readlines(block_size)

            if not lines:
                break

            if sort_key is None:
                lines.sort()
            else:
                lines.sort(key=sort_key)

            self.write_block(''.join(lines), i)
            i += 1

    def cleanup(self):
        map(lambda f: os.remove(f), self.block_filenames)


class BZ2FileSplitter(FileSplitter):
    # BLOCK_FILENAME_FORMAT = 'block_{0}.bz2'

    def get_file_obj(self, filename, mode):
        return bz2.BZ2File(filename, mode)


class FileMerger(object):
    def __init__(self, merge_strategy):
        self.merge_strategy = merge_strategy

    def get_file_obj(self, filename, mode, buffer_size):
        return open(filename, mode, buffer_size)

    def merge(self, filenames, outfilename, buffer_size):
        outfile = self.get_file_obj(outfilename, 'w', buffer_size)
        buffers = FilesArray(self.get_file_handles(filenames, buffer_size))

        while buffers.refresh():
            min_index = self.merge_strategy.select(buffers.get_dict())
            outfile.write(buffers.unshift(min_index))

    def get_file_handles(self, filenames, buffer_size):
        files = {}

        for i in range(len(filenames)):
            files[i] = open(filenames[i], 'r', buffer_size)

        return files


class BZ2FileMerger(FileMerger):
    def get_file_obj(self, filename, mode, buffer_size):
        return bz2.BZ2File(filename, mode, buffer_size)


class NWayMerge(object):
    def select(self, choices):
        min_index = -1
        min_str = None

        for i in range(len(choices)):
            if min_str is None or choices[i] < min_str:
                min_index = i

        return min_index


class FilesArray(object):
    def __init__(self, files):
        self.files = files
        self.empty = set()
        self.num_buffers = len(files)
        self.buffers = {i: None for i in range(self.num_buffers)}

    def get_dict(self):
        return {i: self.buffers[i] for i in range(self.num_buffers) if i not in self.empty}

    def refresh(self):
        for i in range(self.num_buffers):
            if self.buffers[i] is None and i not in self.empty:
                self.buffers[i] = self.files[i].readline()

                if self.buffers[i] == '':
                    self.empty.add(i)

        if len(self.empty) == self.num_buffers:
            return False

        return True

    def unshift(self, index):
        value = self.buffers[index]
        self.buffers[index] = None

        return value


if __name__ == '__main__':
    main()
