#define MKS_PROT_BUFF_SIZE_32   4
#define MKS_PROT_BUFF_SIZE_64   8
#define MKS_PROT_PIN            3
#define MKS_PROT_BPS            2000

typedef struct {
  uint8_t   addr;
  uint8_t   command;
  uint16_t  data;
} MkSAM32BitProtocol;

typedef struct {
  uint8_t   addr;
  uint8_t   command;
  uint16_t  data;
  uint32_t  reserved;
} MkSAM64BitProtocol;
