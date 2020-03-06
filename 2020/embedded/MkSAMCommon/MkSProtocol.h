#define MAX_LENGTH 64
#define OPCODE_GET_CONFIG_REGISTER                    1
#define OPCODE_SET_CONFIG_REGISTER                    2
#define OPCODE_GET_BASIC_SENSOR_VALUE                 3
#define OPCODE_SET_BASIC_SENSOR_VALUE                 4
#define OPCODE_PAUSE_WITH_TIMEOUT                     5

#define OPCODE_GET_DEVICE_TYPE                        50
#define OPCODE_GET_DEVICE_UUID                        51
#define OPCODE_GET_DEVICE_ADDITIONAL                  52
#define OPCODE_HEARTBEAT                              53

#define MKS_ACK                                       0x1
#define MKS_NACK                                      0x2

#define SYNC_REQUEST                                  0x1
#define SYNC_RESPONSE                                 0x2
#define ASYNC                                         0x3

struct mks_header {
  unsigned char   magic_number[2];
  unsigned char   direction;
  unsigned char   op_code;
  unsigned char   content_length;
};
