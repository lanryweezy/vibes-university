from PIL import Image, ImageDraw, ImageFont
import os

def create_og_image():
    # Dimensions for Twitter/Facebook OG image
    width = 1200
    height = 630

    # Create image with dark background
    image = Image.new('RGB', (width, height), color=(15, 23, 42)) # #0f172a
    draw = ImageDraw.Draw(image)

    # Add some "vibe" - orange gradient/shapes
    # Orange: #ff6b35 -> (255, 107, 53)
    draw.rectangle([0, 0, width, 10], fill=(255, 107, 53)) # Top border
    draw.rectangle([0, height-10, width, height], fill=(255, 107, 53)) # Bottom border

    # Add a glowing circle or accent
    draw.ellipse([width-300, -100, width+100, 300], outline=(255, 107, 53), width=2)
    draw.ellipse([width-280, -80, width+80, 280], outline=(255, 107, 53), width=1)

    # Try to load a font, fallback to default
    try:
        # Common paths for fonts on Linux
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        ]
        font_title = None
        for path in font_paths:
            if os.path.exists(path):
                font_title = ImageFont.truetype(path, 80)
                font_subtitle = ImageFont.truetype(path, 40)
                font_tagline = ImageFont.truetype(path, 30)
                break

        if not font_title:
            font_title = ImageFont.load_default()
            font_subtitle = ImageFont.load_default()
            font_tagline = ImageFont.load_default()

    except Exception:
        font_title = ImageFont.load_default()
        font_subtitle = ImageFont.load_default()
        font_tagline = ImageFont.load_default()

    # Draw Text
    draw.text((80, 150), "VIBES UNIVERSITY", fill=(255, 107, 53), font=font_title)
    draw.text((80, 260), "Master AI, Escape the Economic Collapse", fill=(255, 255, 255), font=font_subtitle)

    draw.rectangle([80, 340, 200, 345], fill=(255, 107, 53)) # Divider

    tagline = "Join thousands building AI-powered income streams today."
    draw.text((80, 380), tagline, fill=(148, 163, 184), font=font_tagline)

    # Footer info
    draw.text((80, 520), "vibesuniversity.com", fill=(255, 107, 53), font=font_tagline)

    # Save the image
    output_path = "static/images/og-main.png"
    image.save(output_path)
    print(f"OG Image saved to {output_path}")

if __name__ == "__main__":
    create_og_image()
