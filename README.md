### this project has 3 projects, OBJ To Shape Renderer, Image to colormap, and Texture stitcher.

OBJ to Shape Renderer: converts OBJ models to DF code to render them as text displays.

Image to colormap: converts an image to DF colormap to render the texture on a shape thats
text displays

Texture stitcher: stitches more than 1 OBJ model and textures into 1 OBJ and 1 texture.

## OBJ to Shape Renderer:
click Open Text Display Mesher (colors are dif cus it's not mine thank Cymaera for
making the OBJ to command converter) and
upload your OBJ and texture, then scroll down to the commands section and click Copy (models
must be under 1300 triangles [for normal DF plots] cus 3 displays per triangle)

then paste those commands in the text area in the GUI and click send to diamond fire and place
the templates you get (must have code client to get them) and to export texture data click
export as texture list

## Image to colormap

converts an image (Noise) to a list of colors for sphere model or others, (I recommend just 
doing a sphere model instead of template, it's way better than the template)

## Texture Stitcher

stitches more than 1 texture in a model into 1 model and 1 texture. (some models don't work
and 3d view is a bit weird sometimes)

## Installation

Python 3.12 required. (not any newer sorry, I would use an IDE like pycharm to select what
python version)

clone the repo
```
git clone https://github.com/RedstoneMaster011/ShapeRenderer
```
and run 
```
pip install -r requirements.txt
```
then you can run any of the python files (other than mesher_viewer.py) and run that program