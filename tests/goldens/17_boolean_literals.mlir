module {
  func.func @always_true() -> i1 {
    %0 = arith.constant true
    return %0 : i1
  }

  func.func @always_false() -> i1 {
    %0 = arith.constant false
    return %0 : i1
  }
}
