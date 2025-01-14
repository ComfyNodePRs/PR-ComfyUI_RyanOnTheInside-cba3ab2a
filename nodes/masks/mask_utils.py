import numpy as np
import cv2
from scipy import ndimage
from scipy.ndimage import gaussian_filter


def apply_easing(t, easing_type):
    if easing_type == 'linear':
        return t
    elif easing_type == 'ease_in_out':
        return t**2 * (3 - 2*t)
    elif easing_type == 'bounce':
        return 1 - (1 - t)**2 * np.sin(t * np.pi * 5)**2
    elif easing_type == 'elastic':
        return t**2 * np.sin(10 * np.pi * t)
    else:
        return t  # Default to linear if invalid type

def create_distance_transform(mask):
    mask_8bit = (mask * 255).astype(np.uint8)
    return cv2.distanceTransform(mask_8bit, cv2.DIST_L2, 5)

def normalize_array(arr):
    return (arr - arr.min()) / (arr.max() - arr.min())

def apply_blur(mask, blur_amount):
    return ndimage.gaussian_filter(mask, sigma=blur_amount)

def morph_mask(mask, morph_type, kernel_size, iterations, progress_callback=None):
    kernel = np.ones((kernel_size, kernel_size), np.uint8)
    for _ in range(iterations):
        if morph_type == "erode":
            mask = cv2.erode(mask, kernel, iterations=1)
        elif morph_type == "dilate":
            mask = cv2.dilate(mask, kernel, iterations=1)
        elif morph_type == "open":
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        elif morph_type == "close":
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        
        if progress_callback:
            progress_callback()
    
    return mask

###TRANSFORM
def warp_affine(mask: np.ndarray, M: np.ndarray) -> np.ndarray:
    height, width = mask.shape[:2]
    return cv2.warpAffine(mask, M, (width, height), borderMode=cv2.BORDER_REPLICATE)

def translate_mask(mask: np.ndarray, x_value: float, y_value: float) -> np.ndarray:
    M = np.float32([[1, 0, x_value],
                    [0, 1, y_value]])
    return warp_affine(mask, M)

def rotate_mask(mask: np.ndarray, angle: float) -> np.ndarray:
    height, width = mask.shape[:2]
    center = (width // 2, height // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1)
    return warp_affine(mask, M)

def scale_mask(mask: np.ndarray, scale_x: float, scale_y: float) -> np.ndarray:
    height, width = mask.shape[:2]
    M = cv2.getAffineTransform(
        np.float32([[0, 0], [width, 0], [0, height]]),
        np.float32([[0, 0], [width * scale_x, 0], [0, height * scale_y]])
    )
    return warp_affine(mask, M)

def transform_mask(mask: np.ndarray, transform_type: str, x_value: float, y_value: float) -> np.ndarray:
    if transform_type == "translate":
        return translate_mask(mask, x_value, y_value)
    elif transform_type == "rotate":
        return rotate_mask(mask, x_value)
    elif transform_type == "scale":
        return scale_mask(mask, 1 + x_value, 1 + y_value)
    else:
        raise ValueError(f"Unknown transform type: {transform_type}")
###TRANSFORM


##MASK MATH
def add_masks(mask_a: np.ndarray, mask_b: np.ndarray, strength: float) -> np.ndarray:
    return np.clip(mask_a + mask_b * strength, 0, 1)

def subtract_masks(mask_a: np.ndarray, mask_b: np.ndarray, strength: float) -> np.ndarray:
    return np.clip(mask_a - mask_b * strength, 0, 1)

def multiply_masks(mask_a: np.ndarray, mask_b: np.ndarray, strength: float) -> np.ndarray:
    return mask_a * (mask_b * strength + (1 - strength))

def minimum_masks(mask_a: np.ndarray, mask_b: np.ndarray, strength: float) -> np.ndarray:
    return np.minimum(mask_a, mask_b * strength + mask_a * (1 - strength))

def maximum_masks(mask_a: np.ndarray, mask_b: np.ndarray, strength: float) -> np.ndarray:
    return np.maximum(mask_a, mask_b * strength + mask_a * (1 - strength))

def combine_masks(mask_a: np.ndarray, mask_b: np.ndarray, combination_method: str, strength: float) -> np.ndarray:
    if combination_method == "add":
        return add_masks(mask_a, mask_b, strength)
    elif combination_method == "subtract":
        return subtract_masks(mask_a, mask_b, strength)
    elif combination_method == "multiply":
        return multiply_masks(mask_a, mask_b, strength)
    elif combination_method == "minimum":
        return minimum_masks(mask_a, mask_b, strength)
    elif combination_method == "maximum":
        return maximum_masks(mask_a, mask_b, strength)
    else:
        raise ValueError(f"Unknown combination method: {combination_method}")
    
##MASK MATH

###MASK WARP

def generate_perlin_noise(height: int, width: int, frequency: float, octaves: int) -> np.ndarray:
    noise = np.zeros((2, height, width))
    for _ in range(2):  # Generate noise for both x and y directions
        for i in range(octaves):
            freq = frequency * (2 ** i)
            amp = 1.0 / (2 ** i)
            noise[_] += amp * gaussian_filter((np.random.rand(height, width) * 2 - 1), sigma=1/freq)
    return noise

def generate_radial_displacement(height: int, width: int) -> np.ndarray:
    y, x = np.meshgrid(np.linspace(-1, 1, height), np.linspace(-1, 1, width), indexing='ij')
    r = np.sqrt(x**2 + y**2)
    theta = np.arctan2(y, x)
    dx = r * np.cos(theta)
    dy = r * np.sin(theta)
    return np.stack([dx, dy])

def generate_swirl_displacement(height: int, width: int) -> np.ndarray:
    y, x = np.meshgrid(np.linspace(-1, 1, height), np.linspace(-1, 1, width), indexing='ij')
    r = np.sqrt(x**2 + y**2)
    theta = np.arctan2(y, x)
    dx = r * np.cos(theta + r)
    dy = r * np.sin(theta + r)
    return np.stack([dx, dy])

def apply_displacement(mask: np.ndarray, displacement: np.ndarray, amplitude: float) -> np.ndarray:
    height, width = mask.shape
    y, x = np.meshgrid(np.arange(height), np.arange(width), indexing='ij')

    dx = displacement[0] * amplitude
    dy = displacement[1] * amplitude

    x_warped = np.clip(x + dx, 0, width - 1).astype(np.float32)
    y_warped = np.clip(y + dy, 0, height - 1).astype(np.float32)

    return cv2.remap(mask, x_warped, y_warped, cv2.INTER_LINEAR)

def warp_mask(mask: np.ndarray, warp_type: str, frequency: float, amplitude: float, octaves: int) -> np.ndarray:
    height, width = mask.shape

    if warp_type == "perlin":
        displacement = generate_perlin_noise(height, width, frequency, octaves)
    elif warp_type == "radial":
        displacement = generate_radial_displacement(height, width)
    elif warp_type == "swirl":
        displacement = generate_swirl_displacement(height, width)
    else:
        raise ValueError(f"Unknown warp type: {warp_type}")

    return apply_displacement(mask, displacement, amplitude)

###MASK WARP

def calculate_optical_flow(frame1, frame2, flow_method):
    gray1 = cv2.cvtColor(frame1, cv2.COLOR_RGB2GRAY)
    gray2 = cv2.cvtColor(frame2, cv2.COLOR_RGB2GRAY)
    height, width = gray1.shape

    if flow_method == "Farneback":
        return cv2.calcOpticalFlowFarneback(gray1, gray2, None, 0.5, 3, 15, 3, 5, 1.2, 0)
    elif flow_method in ["LucasKanade", "PyramidalLK"]:
        if flow_method == "LucasKanade":
            feature_params = dict(maxCorners=3000, qualityLevel=0.01, minDistance=7, blockSize=7)
            lk_params = dict(winSize=(15, 15), maxLevel=2, criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03))
        else:  # PyramidalLK
            feature_params = dict(maxCorners=3000, qualityLevel=0.01, minDistance=7, blockSize=7)
            lk_params = dict(winSize=(21, 21), maxLevel=3, criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03))

        p0 = cv2.goodFeaturesToTrack(gray1, mask=None, **feature_params)
        if p0 is None:
            return np.zeros((height, width, 2), dtype=np.float32)

        p1, st, err = cv2.calcOpticalFlowPyrLK(gray1, gray2, p0, None, **lk_params)
        
        flow = np.zeros((height, width, 2), dtype=np.float32)
        if p1 is not None:
            good_new = p1[st==1]
            good_old = p0[st==1]
            for i, (new, old) in enumerate(zip(good_new, good_old)):
                a, b = new.ravel()
                c, d = old.ravel()
                if 0 <= int(b) < height and 0 <= int(a) < width:
                    flow[int(b), int(a)] = [c-a, d-b]
        
        # Amplify the sparse flow
        flow *= 25.0  # Increase this factor to make the effect stronger
        
        # Convert sparse flow to dense flow
        dense_flow = cv2.dilate(flow, None, iterations=3)
        dense_flow = cv2.GaussianBlur(dense_flow, (15, 15), 0)  # Increased kernel size for more spread
        
        # Further amplify the dense flow
        dense_flow *= 20.0  # Increase this factor to make the effect even stronger
        
        return dense_flow
    else:
        raise ValueError(f"Unknown flow method: {flow_method}")