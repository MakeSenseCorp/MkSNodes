struct basic_sensor {
  unsigned char id;
  unsigned char type;
  unsigned short value;
};

struct arduino_nano_usb_sensor {
  unsigned char id;
  unsigned short value;
};

struct arduino_nano_usb_button_click {
  unsigned char id;
  unsigned char value;
};

struct arduino_nano_led_blink {
  unsigned char   pin;
  unsigned short  delay;
};

