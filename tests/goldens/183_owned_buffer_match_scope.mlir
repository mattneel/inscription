module {
  func.func @match_owned(%mode: i8) -> i32 {
    %0 = arith.constant 0 : i32
    %2 = arith.constant 0 : i8
    %3 = arith.cmpi eq, %mode, %2 : i8
    %1 = scf.if %3 -> (i32) {
      %4 = arith.constant 2 : i32
      %5 = arith.index_cast %4 : i32 to index
      %6 = memref.alloc(%5) : memref<?xi32>
      %7 = arith.constant 5 : i32
      %8 = arith.constant 0 : index
      %9 = arith.constant 1 : index
      scf.for %10 = %8 to %5 step %9 {
        memref.store %7, %6[%10] : memref<?xi32>
      }
      %11 = arith.constant 0 : index
      %12 = memref.load %6[%11] : memref<?xi32>
      memref.dealloc %6 : memref<?xi32>
      scf.yield %12 : i32
    } else {
      %14 = arith.constant 1 : i8
      %15 = arith.cmpi eq, %mode, %14 : i8
      %13 = scf.if %15 -> (i32) {
        %16 = arith.constant 4 : i32
        %17 = arith.index_cast %16 : i32 to index
        %18 = memref.alloc(%17) : memref<?xi32>
        %19 = arith.constant 9 : i32
        %20 = arith.constant 0 : index
        %21 = arith.constant 1 : index
        scf.for %22 = %20 to %17 step %21 {
          memref.store %19, %18[%22] : memref<?xi32>
        }
        %23 = arith.constant 3 : index
        %24 = memref.load %18[%23] : memref<?xi32>
        memref.dealloc %18 : memref<?xi32>
        scf.yield %24 : i32
      } else {
        %25 = arith.constant 1 : i32
        scf.yield %25 : i32
      }
      scf.yield %13 : i32
    }
    return %1 : i32
  }

  func.func @main() -> i32 {
    %0 = arith.constant 1 : i8
    %1 = func.call @match_owned(%0) : (i8) -> i32
    return %1 : i32
  }
}
