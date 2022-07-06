LDSCRIPT = xdk-asf/saml21j18b_flash.ld
BOOTUP = xdk-asf/startup_saml21.o xdk-asf/system_saml21.o
MCUTYPE=__SAML21J18B__

OBJS=$(BOOTUP) main.o sieve.o

# Tools
CC=arm-none-eabi-gcc
LD=arm-none-eabi-gcc
AR=arm-none-eabi-ar
AS=arm-none-eabi-as

ELF=main.elf

LDFLAGS+=-T$(LDSCRIPT) -mthumb -mcpu=cortex-m0 -Wl,--gc-sections
CFLAGS+=-mcpu=cortex-m0 -mthumb -g
CFLAGS+=-I xdk-asf -I xdk-asf/include -I xdk-asf/cmsis
CFLAGS+=-D$(MCUTYPE)

%.o: %.c
	$(CC) -MD $(CFLAGS) $(filter %.c,$^) -c -o $@

$(ELF): $(OBJS)
	$(LD) $(LDFLAGS) -o $@ $(OBJS) $(LDLIBS)

.PHONY: clean flash debug

clean:
	rm -f $(OBJS) $(OBJS:.o=.d) $(ELF)

flash debug: %: $(ELF)
	arm-none-eabi-gdb -x $@.gdb $(ELF)

-include $(OBJS:.o=.d)
