#include <VirtualWire.h>
#include <EEPROM.h>
#include "MkSAMProt.h"
#include "MkSProtocol.h"
#include "MkSDeviceStructure.h"
#include "MkSSensor.h"
#include "MkSAMCommon.h"

#define OPCODE_SET_ADDRESS 150
#define OPCODE_SENSOR_VALUE 10

#define NO_MOTION   0
#define MOTION      1
#define PIR_PIN     5

NodeState state = { 0 };
uint8_t pir_read_delay_index = 4;
uint16_t prev_pir_state = NO_MOTION;
uint16_t pir_read_delay[5] = {2000, 1000, 500, 250, 1};

unsigned char DEVICE_TYPE[] = { '2','0','2','0' };
unsigned char DEVICE_SUB_TYPE = 0x4;

mks_header*   uart_tx_header;
unsigned char uart_tx_buffer[MAX_LENGTH];
unsigned char uart_tx_buffer_length;

mks_header*   uart_rx_header;
unsigned char uart_rx_buffer[MAX_LENGTH];

uint8_t rf_tx_buffer[MKS_PROT_BUFF_SIZE_32] = {0};
MkSAM32BitProtocol * ptr_packet = (MkSAM32BitProtocol *)rf_tx_buffer;

uint8_t me_addr = 1;
uint32_t ticker = 1;

void init_network(void) {
  vw_set_tx_pin(MKS_PROT_PIN);  // pin
  vw_setup(MKS_PROT_BPS);       // bps
}

void setup() {
  Serial.begin(9600);
  delay(10);
  Serial.println("Loading Firmware ...");
  
  memset(uart_tx_buffer, 0, MAX_LENGTH);
  uart_tx_header = (mks_header *)(&uart_tx_buffer[0]);

  memset(uart_rx_buffer, 0, MAX_LENGTH);
  uart_rx_header = (mks_header *)(&uart_rx_buffer[0]);

  uart_tx_header->magic_number[0] = 0xDE;
  uart_tx_header->magic_number[1] = 0xAD;
  uart_tx_header->direction       = SYNC_RESPONSE;
  uart_tx_header->op_code         = 0x2;
  uart_tx_header->content_length  = 0x0;
  uart_tx_buffer[6] = '\n';

  pinMode(PIR_PIN, INPUT);
  pinMode(LED_BUILTIN, OUTPUT);
  me_addr = EEPROM.read(0);
  ptr_packet->addr      = me_addr;
  ptr_packet->command   = OPCODE_SENSOR_VALUE;
  ptr_packet->data      = NO_MOTION;
  init_network();
}

void send_motion() {
    vw_send(rf_tx_buffer, MKS_PROT_BUFF_SIZE_32); 
    vw_wait_tx(); 
}

void loop() {
  if (Serial.available() > 0) {
    delay(100);
    int len = Serial.readBytesUntil('\n', uart_rx_buffer, MAX_LENGTH);

    if (uart_rx_buffer[0] != 0xDE || uart_rx_buffer[1] != 0xAD) {
      uart_rx_buffer[len] = '\n';
      Serial.write(&uart_rx_buffer[0], len + 1);
    } else {
      switch (uart_rx_header->op_code) {
        case OPCODE_GET_DEVICE_TYPE: {
          uart_tx_header->direction      = SYNC_RESPONSE;
          uart_tx_header->op_code        = OPCODE_GET_DEVICE_TYPE;
          uart_tx_header->content_length = sizeof(DEVICE_TYPE);
          uart_tx_buffer_length          = sizeof(mks_header) + sizeof(DEVICE_TYPE);

          memcpy((unsigned char *)&uart_tx_buffer[sizeof(mks_header)], DEVICE_TYPE, sizeof(DEVICE_TYPE));
  
          uart_tx_buffer[uart_tx_buffer_length]     = 0xAD;
          uart_tx_buffer[uart_tx_buffer_length + 1] = 0xDE;
          Serial.write(&uart_tx_buffer[0], uart_tx_buffer_length + 2);
        }
        break;
        case OPCODE_GET_DEVICE_ADDITIONAL: {
          uart_tx_header->direction      = SYNC_RESPONSE;
          uart_tx_header->op_code        = OPCODE_GET_DEVICE_ADDITIONAL;
          uart_tx_header->content_length = 2;
          uart_tx_buffer_length          = sizeof(mks_header) + 2;

          uart_tx_buffer[sizeof(mks_header)]        = DEVICE_SUB_TYPE;
          uart_tx_buffer[sizeof(mks_header)+1]      = me_addr;
          uart_tx_buffer[uart_tx_buffer_length]     = 0xAD;
          uart_tx_buffer[uart_tx_buffer_length + 1] = 0xDE;
          Serial.write(&uart_tx_buffer[0], uart_tx_buffer_length + 2);
        }
        break;
        case OPCODE_SET_ADDRESS: {
          uart_tx_header->direction      = SYNC_RESPONSE;
          uart_tx_header->op_code        = OPCODE_SET_ADDRESS;
          uart_tx_header->content_length = 1;
          uart_tx_buffer_length          = sizeof(mks_header) + 1;

          EEPROM.write(0, uart_rx_buffer[sizeof(mks_header)]);
          me_addr = EEPROM.read(0);

          uart_tx_buffer[sizeof(mks_header)]        = me_addr;
          uart_tx_buffer[uart_tx_buffer_length]     = 0xAD;
          uart_tx_buffer[uart_tx_buffer_length + 1] = 0xDE;
          Serial.write(&uart_tx_buffer[0], uart_tx_buffer_length + 2);
        }
        break;
        default: {
          uart_rx_buffer[len] = '\n';
          Serial.write(&uart_rx_buffer[0], len + 1);
		    }
        break;
      }
    }
  } else {
    // PIR logic here
    if (ticker % pir_read_delay[pir_read_delay_index] == 0) {
        ptr_packet->data = (uint16_t)digitalRead(PIR_PIN);
        digitalWrite(LED_BUILTIN, ptr_packet->data);

        if (pir_read_delay_index < 4) {
            pir_read_delay_index++;
            send_motion();
        }

        if (prev_pir_state != ptr_packet->data) {
            prev_pir_state = ptr_packet->data;
            pir_read_delay_index = 0;
            send_motion();
        }
    }

    if (ticker % (1000 * 10) == 0) {
        send_motion();
    }

    ticker++;
    delay(1);
  }
}
