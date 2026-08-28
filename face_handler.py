import cv2
import numpy as np
import base64
import os
import threading

class FaceHandler:
    def __init__(self, detector_path="models/face_detection_yunet_2023mar.onnx", 
                 recognizer_path="models/face_recognition_sface_2021dec.onnx"):
        
        self.lock = threading.Lock()
        if not os.path.exists(detector_path) or not os.path.exists(recognizer_path):
            raise FileNotFoundError(
                f"Model files not found. Ensure '{detector_path}' and '{recognizer_path}' exist in the workspace."
            )
            
        # Initialize detector with a default size, will be updated per image dynamically
        self.detector = cv2.FaceDetectorYN.create(
            model=detector_path,
            config="",
            input_size=(320, 320),
            score_threshold=0.85,
            nms_threshold=0.3,
            top_k=5000
        )
        
        self.recognizer = cv2.FaceRecognizerSF.create(
            model=recognizer_path,
            config=""
        )
        if hasattr(cv2, 'CascadeClassifier') and hasattr(cv2, 'data') and hasattr(cv2.data, 'haarcascades'):
            cascade_path = os.path.join(cv2.data.haarcascades, "haarcascade_eye.xml")
            if os.path.exists(cascade_path):
                self.eye_detector = cv2.CascadeClassifier(cascade_path)
            else:
                self.eye_detector = None
        else:
            self.eye_detector = None

    def decode_base64_image(self, base64_str):
        """
        Decodes a base64 encoded image string into an OpenCV image (numpy array).
        """
        try:
            if "," in base64_str:
                base64_str = base64_str.split(",")[1]
            img_data = base64.b64decode(base64_str)
            nparr = np.frombuffer(img_data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            return img
        except Exception as e:
            print(f"Error decoding base64 image: {e}")
            return None

    def get_embedding(self, img, min_confidence=0.85, return_aligned=False):
        """
        Detects the best face, aligns/crops it, and extracts the 128-D feature vector.
        Returns a normalized 1D numpy array of shape (128,) or None if no face is detected.
        If return_aligned is True, returns tuple (feat, aligned_face).
        """
        if img is None:
            if return_aligned:
                return None, None
            return None
            
        with self.lock:
            h, w = img.shape[:2]
            # Dynamic input size update for YuNet
            self.detector.setInputSize((w, h))
            
            retval, faces = self.detector.detect(img)
            if faces is None or len(faces) == 0:
                if return_aligned:
                    return None, None
                return None
                
            # Find face with highest confidence score
            best_face = max(faces, key=lambda f: f[14])
            
            if best_face[14] < min_confidence:
                if return_aligned:
                    return None, None
                return None
                
            # Align and crop the face
            aligned_face = self.recognizer.alignCrop(img, best_face)
            
            # Extract features
            embedding = self.recognizer.feature(aligned_face)
            
            # Normalize the embedding to unit vector for robust cosine similarity
            feat = embedding[0]
            norm = np.linalg.norm(feat)
            if norm > 0:
                feat = feat / norm
                
            if return_aligned:
                return feat, aligned_face
            return feat

    def _eye_geometry(self, aligned_face):
        """Return normalized detected-eye geometry for one aligned face."""
        if aligned_face is None:
            return None

        if self.eye_detector is not None and not getattr(self.eye_detector, 'empty', lambda: True)():
            gray = cv2.cvtColor(aligned_face, cv2.COLOR_BGR2GRAY)
            gray = cv2.equalizeHist(gray)
            height, width = gray.shape[:2]
            eyes = self.eye_detector.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=4,
                minSize=(max(8, width // 14), max(8, height // 14))
            )
            eyes = [eye for eye in eyes if eye[1] + eye[3] < height * 0.62]
            eyes = sorted(eyes, key=lambda eye: eye[2] * eye[3], reverse=True)[:2]
            if eyes:
                centers = [
                    ((x + (eye_width / 2)) / width, (y + (eye_height / 2)) / height)
                    for x, y, eye_width, eye_height in eyes
                ]
                areas = [(eye_width / width) * (eye_height / height)
                         for _, _, eye_width, eye_height in eyes]
                return {"count": len(eyes), "centers": centers, "areas": areas}
            return {"count": 0, "centers": [], "areas": []}

        # Fallback eye openness detection using pixel standard deviation and vertical Sobel gradient on aligned face ROIs
        # when CascadeClassifier is unavailable (e.g. OpenCV 5.0+)
        gray = cv2.cvtColor(aligned_face, cv2.COLOR_BGR2GRAY)
        height, width = gray.shape[:2]
        # Precise eye ROI excluding eyebrows (y: 40% to 54%)
        r_eye_box = gray[int(height * 0.40):int(height * 0.54), int(width * 0.23):int(width * 0.45)]
        l_eye_box = gray[int(height * 0.40):int(height * 0.54), int(width * 0.55):int(width * 0.77)]

        if r_eye_box.size == 0 or l_eye_box.size == 0:
            return {"count": 0, "centers": [], "areas": [], "energy": 0.0}

        r_std = float(np.std(r_eye_box))
        l_std = float(np.std(l_eye_box))

        r_sob = float(np.mean(np.abs(cv2.Sobel(r_eye_box, cv2.CV_64F, 0, 1))))
        l_sob = float(np.mean(np.abs(cv2.Sobel(l_eye_box, cv2.CV_64F, 0, 1))))

        r_energy = r_std + r_sob
        l_energy = l_std + l_sob
        total_energy = (r_energy + l_energy) / 2.0

        # An open eye has distinct pupil/sclera contrast (std > 30.0 or energy > 40.0)
        open_r = r_energy > 40.0
        open_l = l_energy > 40.0

        count = (1 if open_r else 0) + (1 if open_l else 0)
        return {
            "count": count,
            "centers": [
                (0.33, 0.46) if open_r else (0.0, 0.0),
                (0.67, 0.46) if open_l else (0.0, 0.0)
            ],
            "areas": [0.05 if open_r else 0.0, 0.05 if open_l else 0.0],
            "energy": total_energy
        }

    def check_blink_liveness(self, images, min_frames=1):
        """Blink requirement removed for direct face scanning."""
        return {
            "passed": True,
            "code": "DIRECT_SCAN",
            "frames": []
        }

    def match_face(self, input_embedding, db_students, threshold=0.4):
        """
        Compares input_embedding (1D numpy array) with database student embeddings.
        db_students: List of dicts, each with 'reg_no' and 'face_embedding' (list of 128 floats)
        Returns a tuple of (reg_no, score) if matched above threshold, else (None, None).
        """
        if input_embedding is None or not db_students:
            return None, None
            
        input_emb_2d = input_embedding.reshape(1, -1).astype(np.float32)
        best_match_reg = None
        best_score = -2.0  # Cosine similarity range is [-1, 1]
        
        for student in db_students:
            db_emb = np.array(student["face_embedding"], dtype=np.float32).reshape(1, -1)
            
            # Using SFace built-in match for Cosine similarity
            score = self.recognizer.match(input_emb_2d, db_emb, cv2.FaceRecognizerSF_FR_COSINE)
            
            if score > best_score:
                best_score = score
                best_match_reg = student["reg_no"]
                
        if best_score >= threshold:
            return best_match_reg, float(best_score)
            
        return None, float(best_score)
