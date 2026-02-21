# Path: d:\New folder (2) - JARVIS\check_camera.py
import cv2

def check_cameras(max_to_test=5):
    print("Searching for available cameras...")
    available_cameras = []
    
    for i in range(max_to_test):
        # Test Default
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            available_cameras.append(f"Index {i} (Default)")
            cap.release()
            continue
            
        # Test DirectShow (Common for Windows problematic cameras)
        cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
        if cap.isOpened():
            available_cameras.append(f"Index {i} (DirectShow)")
            cap.release()
            
    if not available_cameras:
        print("No cameras found! Please check your connection and privacy settings.")
    else:
        print("Found the following cameras:")
        for cam in available_cameras:
            print(f" - {cam}")
        print("\nIf JARVIS is not opening the correct camera, update the index in 'backend/gestures/camera/camera_stream.py'")

if __name__ == "__main__":
    check_cameras()
