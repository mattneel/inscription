module {
  func.func @gcd(%a0: i32, %b0: i32) -> i32 {
    %0:2 = scf.while (%a_before = %a0, %b_before = %b0) : (i32, i32) -> (i32, i32) {
      %1 = arith.constant 0 : i32
      %2 = arith.cmpi ne, %b_before, %1 : i32
      scf.condition(%2) %a_before, %b_before : i32, i32
    } do {
    ^bb0(%a_body: i32, %b_body: i32):
      %3 = arith.remsi %a_body, %b_body : i32
      scf.yield %b_body, %3 : i32, i32
    }
    return %0#0 : i32
  }

  func.func @main() -> i32 {
    %0 = arith.constant 48 : i32
    %1 = arith.constant 18 : i32
    %2 = func.call @gcd(%0, %1) : (i32, i32) -> i32
    return %2 : i32
  }
}
