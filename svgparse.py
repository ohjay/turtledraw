#!/usr/bin/env python
# -*- coding: utf-8 -*-

## Turtle Graphics Demonstration
## CS 61A Discussion 9

## USAGE: `python3 svgparse.py [--scheme] <input filepath>`

##############
# PARAMETERS #
##############

fill_shapes      = False
draw_boundary    = False
step_size        = 0.5
bezier_option    = 'cubic'
cubic_unfinished = True  # good one to play with (to guarantee clipping, set to False)
animation        = False
clip             = True
intersperse      = True  # intersperse group paths to diversify colors

# Python-specific (won't work if converting to Scheme code)
pen_width   = 1  # set to None for default
save_output = False

# Only set these if you actually know the window size
DEFAULT_WINDOW_WIDTH  = 720
DEFAULT_WINDOW_HEIGHT = 675

# Custom viewport size (set to None to use default)
WINDOW_WIDTH_OVERRIDE  = 550  # either an integer or None
WINDOW_HEIGHT_OVERRIDE = 550  # either an integer or None

NO_ANIM_UPDATE      = 'group'  # either 'path' or 'group' (case-sensitive); 'group' is faster but less entertaining
NO_ANIM_UPDATE_RATE = 2000

"""
svgparse.py
Procedural image drawing/conversion using turtle graphics

This script parses SVG files and either draws them using turtle graphics OR converts them into Scheme turtle code.
Of the SVG specification, includes support for <path> elements with `d` attributes and `M` / `c` / `z`
path data commands. Assumes that [fill] colors are determined by an enclosing `g` container.


Specification of supported SVG v1.0 elements and attributes:
---
- <svg>    metadata about image
- width    viewport (pixel) width
- height   viewport (pixel) height
- viewBox  four numbers min-x, min-y, width, and height, which specify the shape of the user coordinate system
- <g>      container used to group SVG elements
- fill     specifies the drawing color within a group
- <path>   specifies a path through control points
- d        defines a path (contains a series of "path descriptions")
- M        move to (x, y), which are absolute coordinates
- m        move by (dx, dy) – relative coordinates
- l        draws a line, dx to the right and dy downward
- c        cubic Bézier curve, where coordinates are specified relative to the intial point
- z        close path


For future reference:
---
The positive x-axis points to the right in both turtle graphics and SVG.
However, the positive y-axis points UP in turtle graphics and DOWN in SVG.
To handle this, we will transform all absolute y-coordinates as y = height - y
before manipulating them within the angle/distance calculator (where +y -> up).

On a related note, (0, 0) in Python turtle graphics denotes the point in the center of the canvas.
In SVG, (0, 0) is assumed to be the top left corner of the canvas.
To handle this, we will transform all points by (-canvas width / 2, -canvas height / 2),
which essentially translates (0, 0) to the bottom left corner of the canvas.

Finally, we will assume that the default window size for Python turtles always holds (even if using Scheme).
If you'd like to override this, please update the WINDOW_{WIDTH, HEIGHT}_OVERRIDE parameters at the top of the file.
We do not explicitly set the window size because the necessary command is not implemented in 61A Scheme.


Scaling:
---
We expand the scope of the canvas to include the entire window, minus a bit of padding around the outer edge.
In other words, we use the window dimensions (minus padding) as the canvas dimensions.

We then rescale coordinates according to the viewBox values and the canvas dimensions,
such that drawings take up the entire screen.


To implement piecewise cubic Bézier curves, for which control points are defined as `c` components:
---
We calculate the points on each piecewise Bézier via the matrix version of the explicit form
B(t) = (1 - t)^3 * P0 + 3(1 - t)^2 * t * P1 + 3(1 - t) * t^2 * P2 + t^3 * P3,
using values of t from 0 to 1, spaced out by STEP_SIZE (a parameter specified at the top of the file).
Ideally, STEP_SIZE should be very small, <= 0.10 at the very least.


To implement piecewise quadratic Bézier curves:
---
For each value of t, we calculate the corresponding curve point via the explicit form
B(t) = (1 - t)^2 * P0 + 2(1 - t) * t * P1 + t^2 * P2.


Result of running the script:
---
if --scheme: Once all of the information is parsed, it is converted into Scheme code
             and saved under the name <input basename>.scm in the folder OUTFOLDER.
otherwise:   The image will be drawn on the fly using turtle graphics.
"""

#################
# BÉZIER CURVES #
#################

import numpy as np
M = np.array([[1, 0, 0, 0], [-3, 3, 0, 0], [3, -6, 3, 0], [-1, 3, -3, 1]])

def cubic_bezier(P0, P1, P2, P3):
    """Returns a D x 2 matrix of points, parameterized by values of t from 0 to 1 with increment STEP_SIZE,
    representing the cubic Bézier curve specified by control points P0 -> P3.
    
    Input: each point should be a tuple consisting of an x- and a y-coordinate.
    """
    t_range = list(np.arange(0, 1, step_size))
    if not cubic_unfinished:
        t_range.append(1.0)
    t_mat = np.array([[1, t, t * t, t * t * t] for t in t_range])
    P_mat = np.array([P0, P1, P2, P3])
    return np.dot(t_mat, np.dot(M, P_mat))  # optimal chain multiplication order

def quadratic_bezier(P0, P1, P2):
    """Returns a D x 2 matrix of points, parameterized by values of t from 0 to 1 with increment STEP_SIZE,
    representing the cubic Bézier curve specified by control points P0 -> P2.
    
    Input: each point should be a tuple consisting of an x- and a y-coordinate.
    """
    pts = []
    for t in list(np.arange(0, 1, step_size)) + [1.0]:
        pts.append(np.array([
            (1 - t) * (1 - t) * P0[0] + 2 * (1 - t) * t * P1[0] + t * t * P2[0],
            (1 - t) * (1 - t) * P0[1] + 2 * (1 - t) * t * P1[1] + t * t * P2[1],
        ]))
    return np.array(pts)

if bezier_option.startswith('quad'):
    bezier, num_req_pts = quadratic_bezier, 3
else:
    bezier, num_req_pts = cubic_bezier, 4

###################
# TURTLE GRAPHICS #
###################

def turtle_pensize(width):
    """Set the width of the pen."""
    if direct_draw:
        turtle.pensize(width)

def turtle_speed(speed, overwrite=False):
    if direct_draw:
        turtle.speed(speed)
    else:
        with open(outfile, 'w' if overwrite else 'a') as out:
            out.write('(speed %d)\n' % speed)

def turtle_color(color, overwrite=False):
    if direct_draw:
        turtle.color(color)
    else:
        with open(outfile, 'w' if overwrite else 'a') as out:
            out.write('(color "%s")\n' % color)

def turtle_begin_fill():
    if direct_draw:
        turtle.begin_fill()
    else:
        with open(outfile, 'a') as out:
            out.write('(begin_fill)\n')

def turtle_end_fill():
    if direct_draw:
        turtle.end_fill()
    else:
        with open(outfile, 'a') as out:
            out.write('(end_fill)\n')

def turtle_hide():
    if direct_draw:
        turtle.hideturtle()
    else:
        with open(outfile, 'a') as out:
            out.write('(hideturtle)\n')

def turtle_setpos(x, y, overwrite=False, keep_pen_down=False):
    """Moves to a certain position.
    Input: (x, y) - a point in absolute turtle coordinates
    """
    if direct_draw:
        if not keep_pen_down:
            turtle.penup()
        turtle.setposition(x, y)
        if not keep_pen_down:
            turtle.pendown()
    else:
        with open(outfile, 'w' if overwrite else 'a') as out:
            if keep_pen_down:
                out.write('(setposition %f %f)\n' % (x, y))
            else:
                out.write('(penup) (setposition %f %f) (pendown)\n' % (x, y))
    return x, y

def turtle_traverse(pts, setpos=True):
    """Draws straight lines between the given points.
    Input: pts - a D x 2 matrix of points (in absolute turtle coordinates)
    """
    if not direct_draw:
        out = open(outfile, 'a')
    prev_x, prev_y = turtle_clip(*pts[0]) if clip else pts[0]
    if setpos:
        turtle_setpos(prev_x, prev_y)
    for x, y in pts[1:]:
        if clip:
            x, y = turtle_clip(x, y)
        angle, distance = angle_dist((prev_x, prev_y), (x, y))
        if direct_draw:
            turtle.setheading(angle)
            turtle.forward(distance)
        else:
            out.write('(setheading %f) (forward %f)\n' % (angle, distance))
        prev_x, prev_y = x, y
    if not direct_draw:
        out.close()

################
# PATH DRAWING #
################

from math import sqrt, atan2, pi

def angle_dist(P0, P1):
    """Calculates and returns an (angle, distance) tuple from point (x0, y0) to point (x1, y1).
    The angle represents the clockwise rotation in degrees from a north-facing orientation.
    Essentially, this function demystifies the vector from P0 to P1.
    
    +x -> right
    +y -> up
    
    >>> ad1 = angle_dist((1, 2), (3, 4))
    >>> round(ad1[0], 1)
    45.0
    >>> round(ad1[1], 2)
    2.83
    >>> north, _ = angle_dist((2, 1), (2, 2))
    >>> north
    0.0
    >>> east, _ = angle_dist((2, 1), (3, 1))
    >>> east
    90.0
    >>> south, _ = angle_dist((2, 1), (2, 0))
    >>> south
    180.0
    >>> west, _ = angle_dist((2, 1), (1, 1))
    >>> west
    270.0
    """
    P0_x, P0_y = P0
    P1_x, P1_y = P1
    distance = sqrt((P0_x - P1_x) * (P0_x - P1_x) + (P0_y - P1_y) * (P0_y - P1_y))
    dx, dy = P1_x - P0_x, P1_y - P0_y
    theta_rad = atan2(dy, dx)
    theta = theta_rad * 180 / pi  # measured counterclockwise from the +x axis
    return (450 - theta) % 360, distance

def parse_path(Mx, My, clz):
    """Parses the path and writes the corresponding Scheme code to OUTFILE.
    Incidentally, our piecewise Bézier curves should involve 4 + 3n control points (for some n).
    
    It doesn't affect anything in this function,
    but since we're still assuming the SVG coordinate system at this point,
    +x -> right
    +y -> down

    Input:
    - Mx, My: integer (x, y) starting point coordinates
    - clz: the path description as a list of string coordinates and `c` / `l` / `z` / `m` labels
    """
    mode, close = None, False
    ctrl_pts_svg = [(Mx, My)]
    ctrl_pts_tur = [svg_to_turtle(Mx, My)]
    turtle_setpos(*ctrl_pts_tur[-1])
    prev_move_svg = ctrl_pts_svg[-1]

    def _rel_draw(dx, dy):
        abs_pt_svg = (ctrl_pts_svg[-1][0] + dx, ctrl_pts_svg[-1][1] + dy)
        abs_pt_tur = svg_to_turtle(*abs_pt_svg)
        if mode == 'curve' and len(ctrl_pts_tur) < num_req_pts:
            ctrl_pts_svg.append(abs_pt_svg)
            ctrl_pts_tur.append(abs_pt_tur)
        elif mode == 'line':
            turtle_traverse(np.array([ctrl_pts_tur[-1], abs_pt_tur]), setpos=False)
            del ctrl_pts_svg[:]
            del ctrl_pts_tur[:]
            ctrl_pts_svg.append(abs_pt_svg)
            ctrl_pts_tur.append(abs_pt_tur)

        # Output the Bézier curve if possible
        if mode == 'curve' and len(ctrl_pts_tur) == num_req_pts:
            bezier_pts = bezier(*ctrl_pts_tur)
            turtle_traverse(bezier_pts, setpos=False)
            latest_pt_svg = ctrl_pts_svg[-1]
            latest_pt_tur = ctrl_pts_tur[-1]
            del ctrl_pts_svg[:]
            del ctrl_pts_tur[:]
            ctrl_pts_svg.append(latest_pt_svg)
            ctrl_pts_tur.append(latest_pt_tur)

    # Go through two list elements (x- and y-coords) during every iteration
    for dx, dy in zip(*[iter(clz)] * 2):
        if dx[0] == 'c':
            mode, dx = 'curve', dx[1:]
        elif dx[0] == 'l':
            mode, dx = 'line', dx[1:]
        elif dx[0] == 'm':
            curr_pt_svg = (ctrl_pts_svg[-1][0] + int(dx[1:]), ctrl_pts_svg[-1][1] + int(dy))
            curr_pt_tur = svg_to_turtle(*curr_pt_svg)
            turtle_setpos(*curr_pt_tur)
            prev_move_svg = curr_pt_svg
            ctrl_pts_svg = [curr_pt_svg]
            ctrl_pts_tur = [curr_pt_tur]
            continue
        elif dx[0].isalpha():
            print('WARNING: unrecognized attribute (%s)' % dx[0])
        if dy[-1] == 'z':
            close, dy = True, dy[:-1]
        dx, dy = int(dx), int(dy)

        _rel_draw(dx, dy)
        if close:
            _rel_draw(prev_move_svg[0] - ctrl_pts_svg[-1][0], prev_move_svg[1] - ctrl_pts_svg[-1][1])
            close = False

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--scheme', '-s', action='store_true')
    parser.add_argument('input_file', type=str, help='___.svg')
    args = parser.parse_args()
    infile = args.input_file
    direct_draw = not args.scheme

    import sys
    python_ver = sys.version_info[0]

    import os
    OUTFOLDER = 'out'
    if not os.path.isdir(OUTFOLDER):
        os.makedirs(OUTFOLDER)
    infile_base = os.path.basename(infile)
    if '.' in infile_base:
        infile_base = infile_base[:infile_base.rfind('.')]
    if direct_draw:
        outfile_ext = 'png' if python_ver >= 3 else 'svg'
    else:
        outfile_ext = 'scm'
    outfile = os.path.join(OUTFOLDER, '%s.%s' % (infile_base, outfile_ext))

    if direct_draw:
        import turtle
        import tkinter
        turtle.title('Turtledraw')
        turtle.mode('logo')
        screen = turtle.getscreen()
        window_width = screen.window_width()
        window_height = screen.window_height()
    else:
        window_width = DEFAULT_WINDOW_WIDTH
        window_height = DEFAULT_WINDOW_HEIGHT

    if WINDOW_WIDTH_OVERRIDE is not None:
        window_width = WINDOW_WIDTH_OVERRIDE
    if WINDOW_HEIGHT_OVERRIDE is not None:
        window_height = WINDOW_HEIGHT_OVERRIDE

    import xml.etree.ElementTree
    svgroot = xml.etree.ElementTree.parse(infile).getroot()

    width = float(svgroot.attrib.get('width', None)[:-2])
    height = float(svgroot.attrib.get('height', None)[:-2])
    vb_min_x, vb_min_y, vb_width, vb_height = svgroot.attrib.get('viewBox', None).split()
    vb_min_x, vb_min_y, vb_width, vb_height = [float(d) for d in (vb_min_x, vb_min_y, vb_width, vb_height)]
    assert vb_min_x == 0 and vb_min_y == 0, 'viewBox translations are not currently supported ' \
                                            '(min-x=%r, min-y=%r)' % (vb_min_x, vb_min_y)

    padding = 20
    canvas_width = window_width - padding * 2
    canvas_height = window_height - padding * 2
    canvas_aspect_ratio = canvas_width / canvas_height
    view_box_aspect_ratio = vb_width / vb_height

    # Compute coordinate transform info
    if canvas_aspect_ratio == view_box_aspect_ratio:
        x_scale = float(canvas_width) / vb_width
        y_scale = float(canvas_height) / vb_height
    elif view_box_aspect_ratio > 1:
        x_scale = float(canvas_width) / vb_width
        y_scale = x_scale
    else:
        y_scale = float(canvas_height) / vb_height
        x_scale = y_scale
    x_shift, y_shift = -float(canvas_width) / 2, -float(canvas_height) / 2  # translation to apply to all coords

    def svg_to_turtle(x, y):
        """Transform (absolute) coordinates in SVG system to (absolute) coordinates in turtle system."""
        return x * x_scale + x_shift, canvas_height - y * y_scale + y_shift

    # Boundary calculations
    turtle_00 = svg_to_turtle(0, 0)
    turtle_w0 = svg_to_turtle(vb_width, 0)
    turtle_wh = svg_to_turtle(vb_width, vb_height)
    turtle_0h = svg_to_turtle(0, vb_height)

    def svg_oob(x, y):
        """True if (x, y) is out-of-bounds in SVG coordinates."""
        return x < 0 or x > vb_width or y < 0 or y > vb_height

    def turtle_oob(x, y):
        """True if (x, y) is out-of-bounds in turtle coordinates."""
        return x < turtle_00[0] or x > turtle_w0[0] or y < turtle_0h[1] or y > turtle_00[1]

    def svg_clip(x, y):
        """Clip (x, y) such that it is in-bounds according to SVG coordinates."""
        return np.clip(x, 0, vb_width), np.clip(y, 0, vb_height)

    def turtle_clip(x, y):
        """Clip (x, y) such that it is in-bounds according to turtle coordinates."""
        return np.clip(x, turtle_00[0], turtle_w0[0]), np.clip(y, turtle_0h[1], turtle_00[1])

    # Overwrite the output file
    turtle_speed(0, overwrite=True)
    if pen_width is not None:
        turtle_pensize(pen_width)

    if direct_draw and not animation:
        turtle.tracer(0, 0)
    if draw_boundary:
        turtle_traverse([turtle_00, turtle_w0, turtle_wh, turtle_0h, turtle_00])

    def intersperse_elements(list_of_lists, end_oriented=False):
        """Given a list of lists [[x00, x01, x02, ...], [x10, x11, ...], [x20, x21, ...], ...],
        yields one element from every list IN ORDER until all of the elements have been exhausted:
        x00, x10, x20, ..., x01, x11, x21, ..., x02, x12, x22, ...

        In other words, traverses a 2D list in column-major order.
        The sublists do not need to be of uniform length; if a sublist has been exhausted
        it will simply be passed over when its turn comes.

        To avoid confusion, the 1D list index will be returned as well
        (specifying from which list the element came).
        """
        max_sublist_len = max([len(sublst) for sublst in list_of_lists])
        len_diffs = [max_sublist_len - len(sublst) for sublst in list_of_lists]
        for r in range(max_sublist_len):
            for c in range(len(list_of_lists)):
                if not end_oriented and r < len(list_of_lists[c]):
                    yield list_of_lists[c][r], c
                elif end_oriented and 0 <= r - len_diffs[c] < len(list_of_lists[c]):
                    yield list_of_lists[c][r - len_diffs[c]], c

    def color_group(g):
        """Sets turtle color according to the 'fill' attribute of the group G.
        Returns True upon success, and False upon failure.
        """
        if g.tag.rstrip()[-1] != 'g':
            return False
        color = g.attrib.get('fill', '#000000').upper()
        turtle_color(color)
        return True

    def handle_path(path):
        """Draws the path specified by PATH.
        Returns True upon success, and False upon failure.
        """
        if path.tag.rstrip()[-4:] != 'path':
            print('WARNING: unrecognized element (%s)' % path.tag.rstrip())
            return False
        d = path.attrib['d'].split()
        Mx, My, clz = int(d[0][1:]), int(d[1]), d[2:]
        if fill_shapes:
            turtle_begin_fill()
        parse_path(Mx, My, clz)
        if fill_shapes:
            turtle_end_fill()
        return True

    def try_do_update(idx):
        """Performs an update if IDX matches up with NO_ANIM_UPDATE_RATE."""
        if (idx + 1) % NO_ANIM_UPDATE_RATE == 0:
            turtle.update()

    if intersperse:
        # Potential problem: largest groups still dominate color space
        groups = list(svgroot)
        END_ORIENTED = True
        for _j, (path, _i) in enumerate(intersperse_elements([list(g) for g in svgroot], END_ORIENTED)):
            if not color_group(groups[_i]):
                continue
            handle_path(path)
            if direct_draw and not animation:
                try_do_update(_j)
    else:
        for _i, g in enumerate(svgroot):
            if not color_group(g):
                continue
            for _j, path in enumerate(g):
                handle_path(path)
                if direct_draw and not animation and NO_ANIM_UPDATE != 'group':
                    try_do_update(_j)
            if direct_draw and not animation and NO_ANIM_UPDATE == 'group':
                try_do_update(_i)

    turtle_hide()
    if direct_draw:
        if not animation:
            turtle.update()
        print('[+] Drawing complete.')
        if save_output:
            # Source for following code: https://stackoverflow.com/a/25051183
            if python_ver >= 3:
                import tempfile
                tmpdir = tempfile.mkdtemp()
                svgfile = os.path.join(tmpdir, 'tmp.svg')
            else:
                svgfile = outfile
            import canvasvg
            ts = turtle.getscreen().getcanvas()
            canvasvg.saveall(svgfile, ts)
            if python_ver >= 3:
                import cairosvg
                with open(svgfile) as svg_input, open(outfile, 'wb') as png_output:
                    cairosvg.svg2png(bytestring=svg_input.read(), write_to=png_output)
                import shutil
                shutil.rmtree(tmpdir)
            print('[+] Output saved to %s.' % outfile)
        turtle.exitonclick()
    else:
        print('[+] Wrote result to %s.' % outfile)
