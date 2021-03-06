import os.path

from aql_testcase import AqlTestCase, skip

from aql.utils import Tempfile, Tempdir, open_file

# ==============================================================================


class TestTempFile(AqlTestCase):

    def test_temp_file(self):
        with Tempfile() as temp_file:

            temp_file.write('1234567890\n1234567890'.encode())
            temp_file.flush()

        self.assertFalse(os.path.isfile(temp_file))

    # ==========================================================

    def test_temp_file_rw(self):
        with Tempfile() as temp_file:

            test_string = '1234567890'

            temp_file.write(test_string.encode())
            temp_file.flush()

            with open(temp_file, "r") as temp_file_rh:
                test_string_read = temp_file_rh.read()
                self.assertEqual(test_string, test_string_read)

    # ==========================================================

    def test_temp_dir(self):
        with Tempdir() as tmp_dir:
            tmp_dir = Tempdir(root_dir=tmp_dir)

            for i in range(10):
                Tempfile(root_dir=tmp_dir, suffix='.tmp').close()

        self.assertFalse(os.path.exists(tmp_dir))

    # ==========================================================

    def test_temp_file_in_use(self):
        with Tempfile() as temp_file:

            temp_file.remove()

            with open_file(temp_file, write=True, binary=True) as f:
                f.write(b'1234567890')

        self.assertFalse(os.path.isfile(temp_file))

    # ==========================================================

    @skip
    def test_temp_mmap(self):
        import mmap

        with Tempfile() as temp_file:

            temp_file.remove()

            with open_file(temp_file, write=True, binary=True) as f:
                f.seek(0)
                f.write(b'\0')
                f.flush()
                mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_WRITE)
                mm.close()

                f.seek(0)
                f.write(b"header")
                f.flush()
                with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_WRITE) as mem:
                    d = range(ord('0'), ord('9'))
                    data = bytearray(d)

                    end_offset = len(data)

                    if end_offset > mem.size():
                        page_size = mmap.ALLOCATIONGRANULARITY
                        new_size = ((end_offset + (page_size - 1)) //
                                    page_size) * page_size

                        mem.resize(new_size)

                    mem[0:end_offset] = data

                    buf = mem[0:end_offset]
                    print("buf: %s" % (buf,))

                    buf = mem[0:10]
                    print("buf: %s" % (buf,))

                    mem.move(3, 1, 5)
                    buf = mem[0:10]
                    print("buf: %s" % (buf,))
