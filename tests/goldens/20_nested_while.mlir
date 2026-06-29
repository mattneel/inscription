module {
  func.func @multiply_by_adding(%a0: i32, %b0: i32) -> i32 {
    %0 = arith.constant 0 : i32
    %1:2 = scf.while (%total_before = %0, %outer_before = %0) : (i32, i32) -> (i32, i32) {
      %2 = arith.cmpi slt, %outer_before, %b0 : i32
      scf.condition(%2) %total_before, %outer_before : i32, i32
    } do {
    ^bb0(%total_body: i32, %outer_body: i32):
      %3 = arith.constant 0 : i32
      %4:2 = scf.while (%total_before_loop1 = %total_body, %inner_before_loop1 = %3) : (i32, i32) -> (i32, i32) {
        %5 = arith.cmpi slt, %inner_before_loop1, %a0 : i32
        scf.condition(%5) %total_before_loop1, %inner_before_loop1 : i32, i32
      } do {
      ^bb0(%total_body_loop1: i32, %inner_body_loop1: i32):
        %6 = arith.constant 1 : i32
        %7 = arith.addi %total_body_loop1, %6 : i32
        %8 = arith.addi %inner_body_loop1, %6 : i32
        scf.yield %7, %8 : i32, i32
      }
      %9 = arith.constant 1 : i32
      %10 = arith.addi %outer_body, %9 : i32
      scf.yield %4#0, %10 : i32, i32
    }
    return %1#0 : i32
  }

  func.func @main() -> i32 {
    %0 = arith.constant 6 : i32
    %1 = arith.constant 7 : i32
    %2 = func.call @multiply_by_adding(%0, %1) : (i32, i32) -> i32
    return %2 : i32
  }
}
