#!/usr/bin/env python3
"""
GPU Batch Job Script for Cloud Run Jobs

This script:
1. Detects GPU availability
2. Prints GPU information
3. Executes a GPU computation (matrix multiplication)
4. Saves results to Google Cloud Storage
5. Exits naturally (triggers job termination and GPU shutdown)

NO long-running processes, NO servers, NO infinite loops.
"""

import os
import sys
from datetime import datetime
import torch

# Add project root to path to import shared utils
sys.path.insert(0, '/workspace')  # In container, project root is mounted at /workspace

from utils.gcs_utils import save_results_to_gcs


def check_gpu():
    """
    Detect and print GPU information.
    Returns True if GPU is available, False otherwise.
    """
    print("=" * 60)
    print("GPU DETECTION MAC-2")
    print("=" * 60)
    
    if torch.cuda.is_available():
        gpu_count = torch.cuda.device_count()
        print(f"✅ CUDA is available")
        print(f"✅ Number of GPUs: {gpu_count}")
        
        for i in range(gpu_count):
            gpu_name = torch.cuda.get_device_name(i)
            print(f"✅ GPU {i}: {gpu_name}")
            
            # Get GPU memory info
            mem_allocated = torch.cuda.memory_allocated(i) / 1024**3
            mem_reserved = torch.cuda.memory_reserved(i) / 1024**3
            print(f"   Memory Allocated: {mem_allocated:.2f} GB")
            print(f"   Memory Reserved: {mem_reserved:.2f} GB")
        
        return True
    else:
        print("❌ CUDA is NOT available")
        print("⚠️  Job will run on CPU (not GPU)")
        return False


def run_gpu_computation():
    """
    Execute a GPU-eligible computation.
    This demonstrates that GPU is actually being used.
    """
    print("\n" + "=" * 60)
    print("GPU COMPUTATION")
    print("=" * 60)
    
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")
    
    # Create large tensors for matrix multiplication
    size = 1000
    print(f"Creating {size}x{size} matrices...")
    
    start_time = datetime.now()
    
    # Allocate tensors on GPU
    matrix_a = torch.randn(size, size, device=device)
    matrix_b = torch.randn(size, size, device=device)
    
    print(f"Performing matrix multiplication on {device}...")
    result = torch.matmul(matrix_a, matrix_b)
    
    # Synchronize to ensure computation is complete
    if torch.cuda.is_available():
        torch.cuda.synchronize()
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    print(f"✅ Computation completed in {duration:.4f} seconds")
    print(f"Result shape: {result.shape}")
    print(f"Result mean: {result.mean().item():.4f}")
    print(f"Result std: {result.std().item():.4f}")
    
    return {
        "device": str(device),
        "matrix_size": size,
        "computation_time_seconds": duration,
        "result_shape": list(result.shape),
        "result_mean": result.mean().item(),
        "result_std": result.std().item(),
    }


def main():
    """
    Main execution flow.
    Job runs once and exits naturally.
    """
    print("🚀 Starting GPU Batch Job")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print(f"Job Name: {os.environ.get('JOB_NAME', 'unknown')}")
    
    # Check if we should actually save to GCS (default: True)
    confirm_save = os.environ.get("CONFIRM_SAVE", "true").lower() == "true"
    
    try:
        # Step 1: Check GPU availability
        gpu_available = check_gpu()
        
        if not gpu_available:
            print("\n⚠️  WARNING: No GPU detected")
            print("⚠️  This job requires GPU but will continue on CPU")
        
        # Step 2: Run GPU computation
        results = run_gpu_computation()
        
        # Step 3: Save results to GCS with confirmation parameter
        save_status = save_results_to_gcs(results, confirm_save=confirm_save)
        print(f"Save status: {save_status}")
        
        # Step 4: Exit successfully
        print("\n" + "=" * 60)
        print("✅ JOB COMPLETED SUCCESSFULLY")
        print("=" * 60)
        print("🛑 Exiting (GPU will auto-stop)")
        
        sys.exit(0)
        
    except Exception as e:
        print("\n" + "=" * 60)
        print("❌ JOB FAILED")
        print("=" * 60)
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
