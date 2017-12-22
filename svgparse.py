#!/usr/bin/env python
# -*- coding: utf-8 -*-

## Turtle Graphics Demonstration
## CS 61A Discussion 9

## USAGE: `python3 svgparse.py [--scheme] <input filepath>`

##############
# PARAMETERS #
##############

fill_shapes   = True
scale         = 0.05
step_size     = 0.10
bezier_option = 'cubic'

"""
svgparse.py
Procedural image drawing/conversion using turtle graphics

This script parses SVG files and either draws them using turtle graphics OR converts them into Scheme turtle code.
Of the SVG specification, includes support for <path> elements with `d` attributes and `M` / `c` / `z`
path data commands. Assumes that [fill] colors are determined by an enclosing `g` container.


Specification of supported SVG v1.0 elements and attributes:
---
- <svg>    metadata about image
- width    (pixel) width
- height   (pixel) height
- viewBox  four numbers min-x, min-y, width, and height, which specify the original-size rectangle shape
- <g>      container used to group SVG elements
- fill     specifies the drawing color within a group
- <path>   specifies a path through control points
- d        defines a path (contains a series of "path descriptions")
- M        move to (x, y), which are absolute coordinates
- m        move by (dx, dy) – relative coordinates
- l        draws a line, dx to the right and dy downward
- c        cubic Bézier curve, where coordinates are specified relatively to the intial point
- z        close path


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
    t_mat = np.array([[1, t, t * t, t * t * t] for t in np.arange(0, 1, step_size)])
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

def turtle_speed(speed, overwrite=False):
    if direct_draw:
        turtle.speed(speed)
    else:
        with open(outfile, 'w' if overwrite else 'a') as out:
            out.write('(speed %d)\n' % speed)

def turtle_setpos(x, y, overwrite=False):
    """Moves to a certain position."""
    if direct_draw:
        turtle.penup()
        turtle.setposition(int(round(x * scale)), int(round(y * scale)))
        turtle.pendown()
    else:
        with open(outfile, 'w' if overwrite else 'a') as out:
            out.write('(penup) (setposition %d %d) (pendown)\n' % (int(round(x * scale)), int(round(y * scale))))
    return x, y

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

def turtle_traverse(pts):
    """Draws straight lines between the given points.
    
    Input: pts: a D x 2 matrix of points (in absolute coordinates)
    """
    if not direct_draw:
        out = open(outfile, 'a')
    prev_x, prev_y = pts[0]
    prev_x, prev_y = round(prev_x * scale), round(prev_y * scale)
    for x, y in pts[1:]:
        x, y = round(x * scale), round(y * scale)
        angle, distance = angle_dist((prev_x, prev_y), (x, y))
        if direct_draw:
            turtle.setheading(angle)
            turtle.forward(distance)
        else:
            out.write('(setheading %.3f) (forward %.3f)\n' % (angle, distance))
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
    
    x -> right
    y -> down
    
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
    
    Input:
    - Mx, My: integer (x, y) starting point coordinates
    - clz: the path description as a list of string coordinates and `c` / `l` / `z` / `m` labels
    """
    mode, close, ctrl_pts = None, False, [(Mx, My)]
    prev_move = turtle_setpos(Mx, My)
    
    def _rel_draw(dx, dy):
        abs_pt = (ctrl_pts[-1][0] + dx, ctrl_pts[-1][1] + dy)
        if mode == 'curve' and len(ctrl_pts) < num_req_pts:
            ctrl_pts.append(abs_pt)
        elif mode == 'line':
            turtle_traverse(np.array([ctrl_pts[-1], abs_pt]))
            del ctrl_pts[:]
            ctrl_pts.append(abs_pt)

        # Output the Bézier curve if possible
        if mode == 'curve' and len(ctrl_pts) == num_req_pts:
            bezier_pts = bezier(*ctrl_pts)
            turtle_traverse(bezier_pts)
            latest_pt = ctrl_pts[-1]
            del ctrl_pts[:]
            ctrl_pts.append(latest_pt)

    # Go through two list elements (x- and y-coords) during every iteration
    for dx, dy in zip(*[iter(clz)] * 2):
        if dx[0] == 'c':
            mode, dx = 'curve', dx[1:]
        elif dx[0] == 'l':
            mode, dx = 'line', dx[1:]
        elif dx[0] == 'm':
            curr_pt = (ctrl_pts[-1][0] + int(dx[1:]), ctrl_pts[-1][1] + int(dy))
            prev_move = turtle_setpos(*curr_pt)
            ctrl_pts = [curr_pt]
            continue
        elif dx[0].isalpha():
            print('WARNING: unrecognized attribute (%s)' % dx[0])
        if dy[-1] == 'z':
            close, dy = True, dy[:-1]
        dx, dy = int(dx), int(dy)

        _rel_draw(dx, dy)
        if close:
            _rel_draw(prev_move[0] - ctrl_pts[-1][0], prev_move[1] - ctrl_pts[-1][1])
            close = False

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--scheme', '-s', action='store_true')
    parser.add_argument('input_file', type=str, help='___.svg')
    args = parser.parse_args()
    infile = args.input_file
    direct_draw = not args.scheme

    if direct_draw:
        import turtle
        import tkinter
        turtle.title('Turtledraw')
        turtle.mode('logo')
    else:
        import os
        OUTFOLDER = 'out'
        if not os.path.isdir(OUTFOLDER):
            os.makedirs(OUTFOLDER)
        infile_base = os.path.basename(infile)
        if '.' in infile_base:
            infile_base = infile_base[:infile_base.rfind('.')]
        outfile = os.path.join(OUTFOLDER, '%s.scm' % infile_base)

    # Overwrite the output file
    turtle_speed(0, overwrite=True)

    import xml.etree.ElementTree
    svgroot = xml.etree.ElementTree.parse(infile).getroot()

    height = float(svgroot.attrib.get('height', None)[:-2])
    width = float(svgroot.attrib.get('width', None)[:-2])
    vb_width, vb_height = svgroot.attrib.get('viewBox', None).split()[-2:]
    scale_x, scale_y = float(vb_height) / height, float(vb_width) / width

    for g in svgroot:
        if g.tag.rstrip()[-1] != 'g':
            continue
        color = g.attrib.get('fill', '#000000').upper()
        turtle_color(color)
        for path in g:
            if path.tag.rstrip()[-4:] != 'path':
                print('WARNING: unrecognized element (%s)' % path.tag.rstrip())
                continue
            d = path.attrib['d'].split()
            Mx, My, clz = int(d[0][1:]), int(d[1]), d[2:]
            if fill_shapes:
                turtle_begin_fill()
            parse_path(Mx, My, clz)
            if fill_shapes:
                turtle_end_fill()

    if direct_draw:
        turtle.exitonclick()
        print('[+] Drawing complete.')
    else:
        print('[+] Wrote result to %s.' % outfile)
