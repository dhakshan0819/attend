import sys
from PIL import Image

def process_logo():
    # Load the converted PDF page
    img_path = '/home/neko/attendance-UI/static/srcas_new_temp-1.png'
    img = Image.open(img_path).convert('RGBA')
    width, height = img.size
    
    # 1. Flood fill from the four corners to make the outer white background transparent
    # We will look for pixels close to white (R > 250, G > 250, B > 250)
    data = img.load()
    
    # Simple BFS flood fill for background pixels
    visited = set()
    queue = [(0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1)]
    for q in queue:
        visited.add(q)
        
    while queue:
        x, y = queue.pop(0)
        r, g, b, a = data[x, y]
        # If it's white or very light grey, make it transparent
        if r > 240 and g > 240 and b > 240:
            data[x, y] = (0, 0, 0, 0)
            
            # Check neighbors
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nx, ny = x + dx, y + dy
                if 0 <= nx < width and 0 <= ny < height:
                    if (nx, ny) not in visited:
                        nr, ng, nb, _ = data[nx, ny]
                        if nr > 240 and ng > 240 and nb > 240:
                            visited.add((nx, ny))
                            queue.append((nx, ny))
                            
    # 2. Crop to the bounding box of the shield on the left side
    # We only scan the left 35% of the image where the shield is
    left_limit = int(width * 0.35)
    
    min_x, min_y = width, height
    max_x, max_y = 0, 0
    
    for y in range(height):
        for x in range(left_limit):
            r, g, b, a = data[x, y]
            if a > 0: # Non-transparent pixel
                if x < min_x: min_x = x
                if y < min_y: min_y = y
                if x > max_x: max_x = x
                if y > max_y: max_y = y
                
    # Find the transparent gap column between the shield and the text
    # We look for a gap of at least 50 consecutive completely transparent columns
    shield_right = max_x
    consec_transparent = 0
    for x in range(min_x, left_limit):
        col_has_pixels = False
        for y in range(min_y, max_y + 1):
            if data[x, y][3] > 0:
                col_has_pixels = True
                break
        if not col_has_pixels:
            consec_transparent += 1
        else:
            if consec_transparent >= 50:
                # The shield ended before this transparent gap started
                shield_right = x - consec_transparent
                break
            consec_transparent = 0

    # Add a small padding around the cropped logo
    padding = 20
    min_x = max(0, min_x - padding)
    min_y = max(0, min_y - padding)
    max_x = min(left_limit, shield_right + padding)
    max_y = min(height, max_y + padding)
    
    print(f"Cropping shield bbox: ({min_x}, {min_y}, {max_x}, {max_y})")
    cropped_img = img.crop((min_x, min_y, max_x, max_y))
    
    # Save the processed image as the new logo
    output_path = '/home/neko/attendance-UI/static/srcas_logo.png'
    cropped_img.save(output_path, 'PNG')
    print("Successfully processed and saved logo to:", output_path)

if __name__ == '__main__':
    process_logo()
