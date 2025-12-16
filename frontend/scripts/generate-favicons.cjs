/**
 * Generate favicon PNGs from SVG source
 * Creates all standard favicon sizes for maximum browser compatibility
 */
const sharp = require('sharp');
const fs = require('fs');
const path = require('path');

const SIZES = [16, 32, 48, 64, 128, 180, 192, 512];
const SVG_PATH = path.join(__dirname, '../public/favicon.svg');
const OUTPUT_DIR = path.join(__dirname, '../public');

async function generateFavicons() {
  const svgBuffer = fs.readFileSync(SVG_PATH);

  console.log('Generating favicons...\n');

  for (const size of SIZES) {
    const outputName = size === 180
      ? 'apple-touch-icon.png'
      : size === 192
        ? 'android-chrome-192x192.png'
        : size === 512
          ? 'android-chrome-512x512.png'
          : `favicon-${size}x${size}.png`;

    const outputPath = path.join(OUTPUT_DIR, outputName);

    await sharp(svgBuffer)
      .resize(size, size)
      .png()
      .toFile(outputPath);

    console.log(`✓ ${outputName} (${size}x${size})`);
  }

  // Generate ICO file (contains 16, 32, 48)
  // Sharp doesn't support ICO natively, so we'll create a combined approach
  console.log('\n✓ All PNG favicons generated!');
  console.log('\nUpdate your index.html with:');
  console.log(`
<link rel="icon" type="image/svg+xml" href="/favicon.svg" />
<link rel="icon" type="image/png" sizes="32x32" href="/favicon-32x32.png" />
<link rel="icon" type="image/png" sizes="16x16" href="/favicon-16x16.png" />
<link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png" />
<link rel="manifest" href="/site.webmanifest" />
`);
}

generateFavicons().catch(console.error);
