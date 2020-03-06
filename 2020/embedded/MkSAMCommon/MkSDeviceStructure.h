typedef struct {
  uint16_t halt   : 1;
  uint16_t pause  : 1;
  uint16_t none   : 14;
  uint32_t pauseTs;
} NodeState;
