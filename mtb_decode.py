#!/usr/bin/python

# example code, copied from:
#   https://interrupt.memfault.com/blog/instruction-tracing-mtb-m33
#

try:
    import gdb
except ImportError:
    raise Exception("This script can only be run within gdb!")

import argparse
import struct


def gdb_address_to_function(address):
    try:
        block = gdb.current_progspace().block_for_pc(address)
        while block is not None:
            if block.function:
                return str(block.function)
            block = block.superblock
    except RuntimeError:
        pass
    return gdb.format_address(address)


def gdb_address_to_function_file_line(address):
    function = gdb_address_to_function(address)
    sal = gdb.find_pc_line(address)
    line = "?" if sal.symtab is None else sal.line
    filename = "?" if sal.symtab is None else sal.symtab.filename
    return (filename, line, function)


def gdb_read_word(address):
    reg_data = gdb.selected_inferior().read_memory(address, 4)
    reg_val = struct.unpack("<I", reg_data)[0]
    return reg_val

def gdb_write_word(address, value: int):
    reg_val = struct.pack("<I", value)
    reg_data = gdb.selected_inferior().write_memory(address, reg_val)


class GdbArgumentParseError(Exception):
    pass


class GdbArgumentParser(argparse.ArgumentParser):
    """Wrap argparse so gdb doesn't exit when a command fails """

    def exit(self, status=0, message=None):
        if message:
            self._print_message(message)
        # Don't call sys.exit()
        raise GdbArgumentParseError()


class Mtb(gdb.Command):
    def __init__(self):
        self.MTB_PERIPHERAL_ADDR = None
        self.MTB_POSITION = None
        self.MTB_MASTER = None
        self.MTB_BASE = None
        super(Mtb, self).__init__("mtb", gdb.COMMAND_STATUS, gdb.COMPLETE_NONE)


    def _determine_awidth(self, original_position_val):
        """
        Awidth is required to correctly turn POSITION values into actual system memory addresses.
        Unfortunately, you can't determine it without writing and reading back the position register.
        Assuming we're in post mortem type situation, halted in gdb, this is fine to do every time.
        See Chapter B1 in the coresight mtb trm for more information (ARM DDI 0486B)
        :param original_position_val: the value to restore to the mtb position register
        :return: 2^address_width, the term needed for later calculations.
        """
        # now, we must determine awidth.  We could let it be provided, and avoid this dance, but if we assume
        # we're stopped to inspect the trace, then this is ok, and "auto" good :)
        mtb_master_val = gdb_read_word(self.MTB_MASTER)
        self.mask = mtb_master_val & 0x1F
        self.mtb_sram_size = 2 ** (self.mask + 4)

        gdb_write_word(self.MTB_POSITION, 0xffffffff)
        aw_source = gdb_read_word(self.MTB_POSITION)
        gdb_write_word(self.MTB_POSITION, original_position_val)
        aw_source &= 0xfffffff8
        aw_n = 0
        # counting bits set
        for i in range(32):
            if aw_source & (1<<i):
                aw_n += 1
        awidth = aw_n + 3
        return 1 << awidth


    def decode(self, base, limit=None):
        self.MTB_PERIPHERAL_ADDR = base
        self.MTB_POSITION = self.MTB_PERIPHERAL_ADDR + 0x0
        self.MTB_MASTER = self.MTB_PERIPHERAL_ADDR + 0x4
        self.MTB_BASE = self.MTB_PERIPHERAL_ADDR + 0xC

        mtb_position_val = gdb_read_word(self.MTB_POSITION)
        aw = self._determine_awidth(mtb_position_val)

        # Now that we have awdith, we can calculate the actual block base using the mask field.
        mtb_base_val = gdb_read_word(self.MTB_BASE)
        mtb_master_val = gdb_read_word(self.MTB_MASTER)
        mask = mtb_master_val & 0x1F
        mtb_sram_size = 2 ** (mask + 4)

        write_offset = mtb_position_val & 0xFFFFFFF8
        write_offset = mtb_base_val + ((write_offset + (aw - (mtb_base_val % aw))) % aw)
        my_mask = 0
        # plus 3, plus one for python loops)
        for x in range(mask + 4):
            my_mask |= (1<<x)
        block_base = write_offset & ~my_mask
        print(f"Ok, block at real: {block_base:#08x} of size: {mtb_sram_size} bytes")


        wrap = mtb_position_val & (1 << 2)

        valid_size = mtb_sram_size if wrap else write_offset
        oldest_pkt = write_offset if wrap else 0

        start = 0 if not limit else max(0, valid_size - limit * 8)

        for offset in range(start, valid_size, 8):
            pkt_addr = block_base + (oldest_pkt + offset) % mtb_sram_size

            # Read the source and destination addresses
            s_addr = gdb_read_word(pkt_addr)
            d_addr = gdb_read_word(pkt_addr + 4)

            bit_a = s_addr & 0x1
            s_addr &= 0xFFFFFFFE

            bit_s = d_addr & 0x1
            d_addr &= 0xFFFFFFFE

            if bit_s:
                print("Begin Trace Session")

            # For every valid packet, display src, dst and instruction info, i.e
            #
            # >S: 0x20000488 - HardFault_Handler @ ./main.c:107
            #  D: 0x200004e0 - mtb_disable @ ./mtb.c:41

            file_s, line_s, func_s = gdb_address_to_function_file_line(s_addr)
            file_d, line_d, func_d = gdb_address_to_function_file_line(d_addr)

            if bit_a:  # Exception or Debug State Entry / Exit
                if s_addr & 0xFFFFFF00 == 0xFFFFFF00:
                    print(">S: {} - Exception Return".format(hex(s_addr)))
                else:
                    print(
                        ">S: {} - Exception (or debug) Entry from {} @ {}:{}".format(
                            hex(s_addr), func_s, file_s, line_s
                        )
                    )
            else:  # Normal branch took place
                print(">S: {} - {} @ {}:{}".format(hex(s_addr), func_s, file_s, line_s))

            print(" D: {} - {} @ {}:{}".format(hex(d_addr), func_d, file_d, line_d))

    def invoke(self, unicode_args, from_tty):
        parser = GdbArgumentParser(description="MTB decode utility")

        parser.add_argument(
            "-l", "--limit", type=int, help="The maximum number of packets to decode"
        )
        parser.add_argument("-M", "--mtb_base", help="Base address of MTB registers", default="0x41006000")

        try:
            args = parser.parse_args(list(filter(None, unicode_args.split(" "))))
        except GdbArgumentParseError:
            return

        self.decode(base=int(args.mtb_base, 0), limit=args.limit)


Mtb()
