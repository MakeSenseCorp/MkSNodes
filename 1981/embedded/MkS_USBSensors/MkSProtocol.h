#define MAX_LENGTH 64
#define OPCODE_GET_CONFIG_REGISTER                    0x1
#define OPCODE_SET_CONFIG_REGISTER                    0x2
#define OPCODE_GET_BASIC_SENSOR_VALUE                 0x3
#define OPCODE_SET_BASIC_SENSOR_VALUE                 0x4
#define OPCODE_PAUSE_WITH_TIMEOUT                     0x5

#define OPCODE_GET_DEVICE_TYPE                        0x50
#define OPCODE_GET_DEVICE_UUID                        0x51

#define OPCODE_GET_ARDUINO_NANO_USB_SENSOR_VALUE      0x100
#define OPCODE_SET_ARDUINO_NANO_USB_SENSOR_VALUE      0x101
#define OPCODE_GET_ARDUINO_NANO_USB_LCD_WINDOW        0x102
#define OPCODE_SET_ARDUINO_NANO_USB_LCD_WINDOW        0x103
#define OPCODE_SET_ARDUINO_NANO_USB_LCD_WINDOW_MISC   0x104
#define OPCODE_SET_ARDUINO_NANO_USB_BUTTON_CLICK      0x105
#define OPCODE_SET_ARDUINO_NANO_USB_LED_BLINK         0x106
#define OPCODE_SET_ARDUINO_NANO_USB_GET_INFO          0x107
#define OPCODE_SET_ARDUINO_NANO_USB_GET_SENSORS       0x108

struct mks_header {
  unsigned char   magic_number[2];
  unsigned short  op_code;
  unsigned char   content_length;
};

