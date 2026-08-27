"""Minimal one-click picker for frozen Phase 4 rectified reference images."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
import tkinter as tk

from PIL import Image, ImageTk

from validation.manual_reference import serialize_confirmed_point


def main() -> int:
    parser = argparse.ArgumentParser(description="Pick one manual validation pixel; no automatic detection is performed.")
    parser.add_argument("--image", required=True, type=Path)
    parser.add_argument("--label", required=True, choices=("static", "wave"))
    parser.add_argument("--points-file", required=True, type=Path)
    args = parser.parse_args()

    try:
        image = Image.open(args.image).convert("RGB")
    except OSError as error:
        raise FileNotFoundError(args.image) from error
    if image.width <= 0 or image.height <= 0:
        raise FileNotFoundError(args.image)
    selected: list[tuple[int, int]] = []
    root = tk.Tk()
    root.title(f"Phase 4 {args.label}: click waterline; Enter/y confirm; Esc cancel")
    canvas = tk.Canvas(root, width=image.width, height=image.height, scrollregion=(0, 0, image.width, image.height))
    horizontal = tk.Scrollbar(root, orient=tk.HORIZONTAL, command=canvas.xview)
    vertical = tk.Scrollbar(root, orient=tk.VERTICAL, command=canvas.yview)
    canvas.configure(xscrollcommand=horizontal.set, yscrollcommand=vertical.set)
    photo = ImageTk.PhotoImage(image)
    canvas.create_image(0, 0, anchor=tk.NW, image=photo)
    canvas.grid(row=0, column=0, sticky="nsew")
    vertical.grid(row=0, column=1, sticky="ns")
    horizontal.grid(row=1, column=0, sticky="ew")
    root.grid_rowconfigure(0, weight=1)
    root.grid_columnconfigure(0, weight=1)
    root.geometry(f"{min(image.width + 20, 1400)}x{min(image.height + 20, 900)}")
    confirmed = {"value": False}

    def on_click(event: tk.Event) -> None:
        u_px, v_px = int(canvas.canvasx(event.x)), int(canvas.canvasy(event.y))
        selected[:] = [(u_px, v_px)]
        canvas.delete("manual_crosshair")
        canvas.create_line(u_px - 14, v_px, u_px + 14, v_px, fill="red", tags="manual_crosshair")
        canvas.create_line(u_px, v_px - 14, u_px, v_px + 14, fill="red", tags="manual_crosshair")
        canvas.create_text(u_px + 12, v_px - 12, text=f"u={u_px}, v={v_px}", fill="red", anchor=tk.SW, tags="manual_crosshair")
        print(f"candidate u={u_px}, v={v_px}")

    def confirm(_event: tk.Event | None = None) -> None:
        if selected:
            confirmed["value"] = True
            root.destroy()

    def cancel(_event: tk.Event | None = None) -> None:
        root.destroy()

    canvas.bind("<Button-1>", on_click)
    root.bind("<Return>", confirm)
    root.bind("y", confirm)
    root.bind("Y", confirm)
    root.bind("<Escape>", cancel)
    root.mainloop()
    if not confirmed["value"]:
        print("cancelled; no file was changed")
        return 1

    width, height = image.size
    u_px, v_px = selected[0]
    serialize_confirmed_point(
        args.points_file, label=args.label, u_px=u_px, v_px=v_px,
        image_width_px=width, image_height_px=height,
    )
    print(f"confirmed {args.label}: u={u_px}, v={v_px}")
    print("pixel uncertainty remains null; fill it manually in the YAML")
    return 0


if __name__ == "__main__":
    sys.exit(main())
