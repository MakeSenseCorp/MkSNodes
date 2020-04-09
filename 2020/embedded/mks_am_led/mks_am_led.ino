#include <VirtualWire.h>
#include <EEPROM.h>
#include "MkSAMProt.h"
#include "MkSProtocol.h"
#include "MkSDeviceStructure.h"
#include "MkSSensor.h"
#include "MkSAMCommon.h"

#define OPCODE_SET_ADDRESS 150

NodeState state = { 0 };

void(* reset_function)(void) = 0;

unsigned char DEVICE_TYPE[] = { '2','0','2','0' };
unsigned char DEVICE_SUB_TYPE = SLAVE;

mks_header*   uart_tx_header;
unsigned char uart_tx_buffer[MAX_LENGTH];
unsigned char uart_tx_buffer_length;

mks_header*   uart_rx_header;
unsigned char uart_rx_buffer[MAX_LENGTH];

uint8_t rf_rx_buffer[MKS_PROT_BUFF_SIZE_32] = {0};
uint8_t rf_rx_buffer_length = MKS_PROT_BUFF_SIZE_32;
MkSAM32BitProtocol * ptr_packet = (MkSAM32BitProtocol *)rf_rx_buffer;

uint8_t me_addr = 1;
uint32_t ticker = 1;

void init_network(void) {
  vw_set_rx_pin(MKS_PROT_PIN);  // pin
  vw_setup(MKS_PROT_BPS);       // bps
  vw_rx_start();
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

  pinMode(LED_BUILTIN, OUTPUT);
  me_addr = EEPROM.read(0);
  init_network();
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
    delay(1);
    if (vw_get_message(rf_rx_buffer, &rf_rx_buffer_length)) {
      if (rf_rx_buffer_length < 4) {
        delay(10);
        reset_function();
      }

      if (ptr_packet->addr == me_addr) {
        switch(ptr_packet->command) {
          case 1:
            if (ptr_packet->data > 0) {
              digitalWrite(LED_BUILTIN, HIGH);
            } else {
              digitalWrite(LED_BUILTIN, LOW);
            }
          break;
        }
      }
    }

    ticker++;
  }
}
