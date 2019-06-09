#include "MkSProtocol.h"
#include "MkSDeviceStructure.h"
#include "MkSSensor.h"

#define MAX_SWITCHES    4
#define DIRECTION_UP    0x1
#define DIRECTION_DOWN  0x2
#define DIRECTION_STOP  0x3
#define NONE            0xFF

struct NodeState {
  uint16_t halt : 1;
  uint16_t pause : 1;
  uint16_t none : 14;

  unsigned long pauseTs;
};

struct NodeSwitch {
  uint8_t pin;
  uint8_t id;
  uint8_t value;
  uint8_t group;
  uint8_t direction;
};

struct NodeInfo {
  uint8_t info_size;
  uint8_t switch_count;
};

unsigned char UUID[] = { 'a','c','6','d','e','8','3','7','-',
                         '7','8','6','3','-',
                         '7','2','a','9','-',
                         'c','7','8','9','-',
                         'b','0','a','a','e','7','e','9','d','9','3','e' };
unsigned char DEVICE_TYPE_NAME[] = { 'A','R','D','U','I','N','O','-',
                                'N','A','N','O','-',
                                'U','S','B'};
unsigned char DEVICE_TYPE[] = { '1','9','8','1'};

mks_header*   tx_header;
unsigned char tx_buffer[MAX_LENGTH];

mks_header*   rx_header;
unsigned char rx_buffer[MAX_LENGTH];

unsigned char tx_buffer_length;
device_config config_register;

struct NodeState state = { 0 };

NodeSwitch switches[MAX_SWITCHES] = { {4, 0x3, LOW, NONE, NONE},
                                      {5, 0x4, LOW, NONE, NONE},
                                      {6, 0x5, LOW, 1, DIRECTION_UP},
                                      {7, 0x6, LOW, 1, DIRECTION_DOWN}
                                    };
NodeInfo node_info = {2, MAX_SWITCHES};

void setup() {
  Serial.begin(9600);
  delay(10);
  
  memset(tx_buffer, 0, MAX_LENGTH);
  tx_header = (mks_header *)(&tx_buffer[0]);

  memset(rx_buffer, 0, MAX_LENGTH);
  rx_header = (mks_header *)(&rx_buffer[0]);

  tx_header->magic_number[0] = 0xDE;
  tx_header->magic_number[1] = 0xAD;
  tx_header->op_code         = 0x2;
  tx_header->content_length  = 0x0;
  tx_buffer[6] = '\n';

  config_register.sensor_update_type  = 0x0;
  config_register.status              = 0x1;
  config_register.sensor_count        = 0x3;
  config_register.reserved            = 0x0;

  pinMode(LED_BUILTIN, OUTPUT);
  for (uint8_t i = 0; i < MAX_SWITCHES; i++) {
    pinMode(switches[i].pin, OUTPUT);
  }
}

void blink () {
  digitalWrite(LED_BUILTIN, HIGH);
  delay(1000);
  digitalWrite(LED_BUILTIN, LOW);
  delay(1000);
}

void loop() {  
  if (Serial.available() > 0) {
    delay(100);
    int len = Serial.readBytesUntil('\n', rx_buffer, MAX_LENGTH);

    if (rx_buffer[0] != 0xDE || rx_buffer[1] != 0xAD) {
      rx_buffer[len] = '\n';
      Serial.write(&rx_buffer[0], len + 1);
    } else {
      switch (rx_header->op_code) {
        case OPCODE_GET_DEVICE_TYPE: {
          tx_header->op_code        = OPCODE_GET_DEVICE_TYPE;
          tx_header->content_length = sizeof(DEVICE_TYPE);
          tx_buffer_length          = sizeof(mks_header) + sizeof(DEVICE_TYPE);

          memcpy((unsigned char *)&tx_buffer[sizeof(mks_header)], DEVICE_TYPE, sizeof(DEVICE_TYPE));
  
          tx_buffer[tx_buffer_length] = '\n';
          Serial.write(&tx_buffer[0], tx_buffer_length + 1);
        }
        break;
        case OPCODE_GET_DEVICE_UUID: {
          tx_header->op_code        = OPCODE_GET_DEVICE_UUID;
          tx_header->content_length = sizeof(UUID);
          tx_buffer_length          = sizeof(mks_header) + sizeof(UUID);

          memcpy((unsigned char *)&tx_buffer[sizeof(mks_header)], UUID, sizeof(UUID));
  
          tx_buffer[tx_buffer_length] = '\n';
          Serial.write(&tx_buffer[0], tx_buffer_length + 1);
        }
        break;
        case OPCODE_GET_CONFIG_REGISTER: {
          // Build response.
          memset((unsigned char *)&tx_buffer[sizeof(mks_header)], 0x0, MAX_LENGTH - sizeof(mks_header));
          memcpy((unsigned char *)&tx_buffer[sizeof(mks_header)], (unsigned char *)&config_register, 1);
          tx_header->op_code        = OPCODE_GET_CONFIG_REGISTER;
          tx_header->content_length = sizeof(device_config);
          tx_buffer_length          = sizeof(mks_header) + sizeof(device_config);
  
          tx_buffer[tx_buffer_length] = '\n';
          Serial.write(&tx_buffer[0], tx_buffer_length + 1);
        }
        break;
        case OPCODE_SET_CONFIG_REGISTER: {
          // Set new configure value.
          memcpy((unsigned char *)&config_register, (unsigned char *)&rx_buffer[sizeof(mks_header)], 1);
  
          // Build response.
          memset((unsigned char *)&tx_buffer[sizeof(mks_header)], 0x0, MAX_LENGTH - sizeof(mks_header));
          memcpy((unsigned char *)&tx_buffer[sizeof(mks_header)], (unsigned char *)&config_register, 1);
          tx_header->op_code        = OPCODE_SET_CONFIG_REGISTER;
          tx_header->content_length = sizeof(device_config);
          tx_buffer_length          = sizeof(mks_header) + sizeof(device_config);
  
          tx_buffer[tx_buffer_length] = '\n';
          Serial.write(&tx_buffer[0], tx_buffer_length + 1);
        }
        break;
        case OPCODE_SET_ARDUINO_NANO_USB_GET_INFO: {
          tx_buffer_length = sizeof(mks_header);
          
          memcpy(&tx_buffer[tx_buffer_length], &node_info, sizeof(NodeInfo));
          tx_buffer_length += sizeof(NodeInfo);
          
          memcpy(&tx_buffer[tx_buffer_length], &switches[0], sizeof(NodeSwitch) * MAX_SWITCHES);
          tx_buffer_length += (sizeof(NodeSwitch) * MAX_SWITCHES);

          tx_header->op_code        = OPCODE_SET_ARDUINO_NANO_USB_GET_INFO;
          tx_header->content_length = tx_buffer_length - sizeof(mks_header);
          
          tx_buffer[tx_buffer_length] = '\n';
          Serial.write(&tx_buffer[0], tx_buffer_length + 1);
        }
        break;
        case OPCODE_SET_ARDUINO_NANO_USB_GET_SENSORS: {
          tx_buffer_length = sizeof(mks_header);
          
          tx_buffer[tx_buffer_length] = MAX_SWITCHES;
          tx_buffer_length++;
          
          memcpy(&tx_buffer[tx_buffer_length], &switches[0], sizeof(NodeSwitch) * MAX_SWITCHES);
          tx_buffer_length += (sizeof(NodeSwitch) * MAX_SWITCHES);

          tx_header->op_code        = OPCODE_SET_ARDUINO_NANO_USB_GET_SENSORS;
          tx_header->content_length = tx_buffer_length - sizeof(mks_header);
          
          tx_buffer[tx_buffer_length] = '\n';
          Serial.write(&tx_buffer[0], tx_buffer_length + 1);
        }
        break;
        case OPCODE_GET_ARDUINO_NANO_USB_SENSOR_VALUE: {
          arduino_nano_usb_sensor* sensor = (arduino_nano_usb_sensor *)&rx_buffer[sizeof(mks_header)];
          tx_buffer_length                = sizeof(mks_header) + sizeof(arduino_nano_usb_sensor);

          switch (sensor->id) {
            case 0x3:
            case 0x4:
            case 0x5:
            case 0x6:
              sensor->value = switches[sensor->id - 0x3].value;
            break;
          }

          memcpy(&tx_buffer[0], &rx_buffer[0], MAX_LENGTH);
          tx_buffer[tx_buffer_length] = '\n';
          Serial.write(&tx_buffer[0], tx_buffer_length + 1);
        }
        break;
        case OPCODE_SET_ARDUINO_NANO_USB_SENSOR_VALUE: {
          arduino_nano_usb_sensor* sensor = (arduino_nano_usb_sensor *)&rx_buffer[sizeof(mks_header)];
          tx_buffer_length                = sizeof(mks_header) + sizeof(arduino_nano_usb_sensor);

          switch (sensor->id) {
            case 0x3:
            case 0x4:
            case 0x5:
            case 0x6:
              switches[sensor->id - 0x3].value = sensor->value;
              if (sensor->value) {
                digitalWrite(switches[sensor->id - 0x3].pin, HIGH);
              } else {
                digitalWrite(switches[sensor->id - 0x3].pin, LOW);
              }
            break;
            default:
            break;
          }

          memcpy(&tx_buffer[0], &rx_buffer[0], MAX_LENGTH);
          tx_buffer[tx_buffer_length] = '\n';
          Serial.write(&tx_buffer[0], tx_buffer_length + 1);
        }
        break;
        case OPCODE_PAUSE_WITH_TIMEOUT:
          state.pause = 0x1;
          state.pauseTs = millis();
        break;
        default:
          rx_buffer[len] = '\n';
          Serial.write(&tx_buffer[0], len + 1);
        break;
      }
    }
  } else {
    delay(50);
    if (state.pause) {
      if (abs(millis() - state.pauseTs) > 500) {
        state.pause = 0x0;
      }
    }
  }
}
