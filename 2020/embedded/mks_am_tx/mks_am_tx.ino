#include <VirtualWire.h>
#include "MkSAMProt.h"
#include "MkSProtocol.h"
#include "MkSDeviceStructure.h"
#include "MkSSensor.h"
#include "MkSAMCommon.h"

#define OPCODE_TX_DATA			100
#define OPCODE_RX_DATA			101

NodeState state = { 0 };

unsigned char DEVICE_TYPE[] = { '2','0','2','0' };
unsigned char DEVICE_SUB_TYPE = MASTER_TX;

mks_header*   uart_tx_header;
unsigned char uart_tx_buffer[MAX_LENGTH];
unsigned char uart_tx_buffer_length;

mks_header*   uart_rx_header;
unsigned char uart_rx_buffer[MAX_LENGTH];

uint8_t rf_tx_buffer[MKS_PROT_BUFF_SIZE_32] = {0};
MkSAM32BitProtocol * ptr_packet = (MkSAM32BitProtocol *)rf_tx_buffer;

uint32_t ticker = 1;

void setup() {
  Serial.begin(9600);
  delay(10);
  
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
  
  vw_set_tx_pin(MKS_PROT_PIN);  // pin
  vw_setup(MKS_PROT_BPS);       // bps
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
          uart_tx_header->content_length = 1;
          uart_tx_buffer_length          = sizeof(mks_header) + 1;

          uart_tx_buffer[sizeof(mks_header)] = DEVICE_SUB_TYPE;
          uart_tx_buffer[uart_tx_buffer_length]     = 0xAD;
          uart_tx_buffer[uart_tx_buffer_length + 1] = 0xDE;
          Serial.write(&uart_tx_buffer[0], uart_tx_buffer_length + 2);
        }
        break;
        case OPCODE_PAUSE_WITH_TIMEOUT: {
          state.pause = 0x1;
          state.pauseTs = millis();
        }
        break;
		    case OPCODE_TX_DATA: {
          // Build response.
          uart_tx_header->direction      = SYNC_RESPONSE;
          uart_tx_header->op_code        = OPCODE_TX_DATA;
          uart_tx_header->content_length = 4;
          uart_tx_buffer_length          = sizeof(mks_header) + 4;

          memcpy((unsigned char *)&rf_tx_buffer[0], (unsigned char *)&uart_rx_buffer[sizeof(mks_header)], MKS_PROT_BUFF_SIZE_32);
          memcpy((unsigned char *)&uart_tx_buffer[sizeof(mks_header)], (unsigned char *)&uart_rx_buffer[sizeof(mks_header)], MKS_PROT_BUFF_SIZE_32);

          vw_send(rf_tx_buffer, MKS_PROT_BUFF_SIZE_32); 
          vw_wait_tx(); 
  
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
    delay(10);
    
    if (ticker % 1000 == 0) {
      if (!state.pause) {
        uart_tx_header->direction                 = ASYNC;
        uart_tx_header->op_code                   = OPCODE_HEARTBEAT;
        uart_tx_header->content_length            = 1;
        uart_tx_buffer_length                     = sizeof(mks_header) + 1;
        uart_tx_buffer[sizeof(mks_header)]        = MKS_ACK;
        uart_tx_buffer[uart_tx_buffer_length]     = 0xAD;
        uart_tx_buffer[uart_tx_buffer_length + 1] = 0xDE;
        Serial.write(&uart_tx_buffer[0], uart_tx_buffer_length + 2);
      }
    }
    
    if (state.pause) {
      if (abs(millis() - state.pauseTs) > 500) {
        state.pause = 0x0;
      }
    }

    ticker++;
  }
}
