module {
  func.func private @host_notify(i32)

  func.func @caller() -> i32 {
    %0 = arith.constant 7 : i32
    func.call @host_notify(%0) : (i32) -> ()
    %1 = arith.constant 0 : i32
    return %1 : i32
  }

  func.func @main() -> i32 {
    %0 = arith.constant 0 : i32
    return %0 : i32
  }
}
