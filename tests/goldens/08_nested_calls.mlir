module {
  func.func @square(%x: i32) -> i32 {
    %0 = arith.muli %x, %x : i32
    return %0 : i32
  }

  func.func @sum(%a: i32, %b: i32) -> i32 {
    %0 = arith.addi %a, %b : i32
    return %0 : i32
  }

  func.func @sum_of_squares(%a: i32, %b: i32) -> i32 {
    %0 = func.call @square(%a) : (i32) -> i32
    %1 = func.call @square(%b) : (i32) -> i32
    %2 = func.call @sum(%0, %1) : (i32, i32) -> i32
    return %2 : i32
  }
}
