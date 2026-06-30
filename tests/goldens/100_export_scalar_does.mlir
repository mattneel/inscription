module {
  func.func @ins_require_nonnegative(%value: i32) {
    %0 = arith.constant 0 : i32
    %1 = arith.cmpi sge, %value, %0 : i32
    cf.assert %1, "require failed at line 2"
    return
  }

  func.func @main() -> i32 {
    %0 = arith.constant 7 : i32
    func.call @ins_require_nonnegative(%0) : (i32) -> ()
    return %0 : i32
  }
}
