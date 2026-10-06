from __future__ import annotations

import json
import math
import os
import shutil
import hashlib
import zipfile
from pathlib import Path
from uuid import uuid4

import cadquery as cq
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from .models import BuildResult, Finding, InspectionFeature, PartSpec, TemplateId
from .store import DATA_DIR


T = 1.6002
R = 1.5875


def validate_spec(spec: PartSpec) -> None:
    if abs(spec.stock_thickness_mm - T) > 0.001:
        raise ValueError("Choose the supported 0.063 inch 5052-H32 stock profile.")
    if len(spec.holes) + len(spec.slots) + len(spec.cutouts) > 100:
        raise ValueError("A design can have at most 100 cut features in this prototype.")
    for name, value in spec.parameters.items():
        if not math.isfinite(value) or not 0.1 <= value <= 1000:
            raise ValueError(f"{name.replace('_', ' ').title()} must be between 0.1 and 1000 mm.")
    for kind, features in (("hole", spec.holes), ("slot", spec.slots), ("cutout", spec.cutouts)):
        for index, feature in enumerate(features, 1):
            if any(not math.isfinite(v) or abs(v) > 1000 for v in feature.values()):
                raise ValueError(f"{kind.title()} {index} contains an invalid dimension.")
            if any(feature.get(d, 0) <= 0 for d in {"hole": ("diameter",), "slot": ("length", "width"), "cutout": ("length", "width")}[kind]):
                raise ValueError(f"{kind.title()} {index} dimensions must be positive.")
    p = spec.parameters
    if spec.template_id == TemplateId.RECT_PLATE:
        x_limit, y_limit, circular = p["length"], p["width"], False
    elif spec.template_id == TemplateId.ROUND_PLATE:
        x_limit = y_limit = p["diameter"] / 2
        circular = True
    else:
        x_limit = p.get("base_length", p.get("base_width", 0))
        y_limit = p.get("width", p.get("length", 0))
        circular = False
    for kind, items in (("hole", spec.holes), ("slot", spec.slots), ("cutout", spec.cutouts)):
        for index, item in enumerate(items, 1):
            sx = item.get("diameter", item.get("length", 0))
            sy = item.get("diameter", item.get("width", 0))
            x, y = item["x"], item["y"]
            if circular:
                # Circular-plate feature coordinates use the plate center as (0, 0).
                radius = p["diameter"] / 2
                if math.hypot(x, y) + math.hypot(sx / 2, sy / 2) > radius + 1e-7:
                    raise ValueError(f"{kind.title()} {index} does not fit inside the circular plate.")
            elif x - sx / 2 < 0 or x + sx / 2 > x_limit or y - sy / 2 < 0 or y + sy / 2 > y_limit:
                raise ValueError(f"{kind.title()} {index} does not fit inside the supported base face.")


def _profile(name: str) -> dict:
    path = Path(__file__).resolve().parents[2] / "suppliers" / "sendcutsend" / "5052-h32-0.063.json"
    data = json.loads(path.read_text())
    data["name"] = name
    return data


def default_spec(template: TemplateId) -> PartSpec:
    parameters: dict[str, float] = {
        "rectangular_plate": {"length": 120, "width": 70},
        "circular_plate": {"diameter": 100},
        "l_bracket": {"base_length": 100, "width": 50, "flange_height": 40, "inside_radius": R},
        "u_channel": {"base_width": 80, "length": 100, "flange_height": 30, "inside_radius": R},
        "z_bracket": {"base_length": 100, "width": 50, "flange_height": 30, "inside_radius": R},
    }[template]
    holes = ([{"x": 15, "y": 15, "diameter": 6.5}, {"x": 105, "y": 15, "diameter": 6.5}, {"x": 15, "y": 55, "diameter": 6.5}, {"x": 105, "y": 55, "diameter": 6.5}] if template == TemplateId.RECT_PLATE else [])
    return PartSpec(template_id=template, parameters=parameters, holes=holes)


def _rect_plate(p: dict[str, float], spec: PartSpec):
    length, width = p["length"], p["width"]
    part = cq.Workplane("XY").box(length, width, spec.stock_thickness_mm, centered=(False, False, False))
    for hole in spec.holes:
        before = part.val().Volume()
        part = part.cut(cq.Workplane("XY").circle(hole["diameter"] / 2).extrude(spec.stock_thickness_mm + 2).translate((hole["x"], hole["y"], -1)))
        if before - part.val().Volume() < 0.01: raise ValueError("Hole did not intersect the plate.")
    for slot in spec.slots:
        before = part.val().Volume()
        part = part.cut(cq.Workplane("XY").center(slot["x"], slot["y"]).slot2D(slot["length"], slot["width"]).extrude(spec.stock_thickness_mm + 2).translate((0, 0, -1)))
        if before - part.val().Volume() < 0.01: raise ValueError("Slot did not intersect the plate.")
    for cutout in spec.cutouts:
        before = part.val().Volume()
        part = part.cut(cq.Workplane("XY").box(cutout["length"], cutout["width"], spec.stock_thickness_mm + 2, centered=(True, True, False)).translate((cutout["x"], cutout["y"], -1)))
        if before - part.val().Volume() < 0.01: raise ValueError("Cutout did not intersect the plate.")
    return part


def _round_plate(p: dict[str, float], spec: PartSpec):
    radius = p["diameter"] / 2
    part = cq.Workplane("XY").circle(radius).extrude(spec.stock_thickness_mm)
    for hole in spec.holes:
        before = part.val().Volume()
        part = part.cut(cq.Workplane("XY").center(hole["x"], hole["y"]).circle(hole["diameter"] / 2).extrude(spec.stock_thickness_mm + 2).translate((0, 0, -1)))
        if before - part.val().Volume() < 0.01: raise ValueError("Hole did not intersect the circular plate.")
    for slot in spec.slots:
        before = part.val().Volume()
        part = part.cut(cq.Workplane("XY").center(slot["x"], slot["y"]).slot2D(slot["length"], slot["width"]).extrude(spec.stock_thickness_mm + 2).translate((0, 0, -1)))
        if before - part.val().Volume() < 0.01: raise ValueError("Slot did not intersect the circular plate.")
    for cutout in spec.cutouts:
        before = part.val().Volume()
        part = part.cut(cq.Workplane("XY").box(cutout["length"], cutout["width"], spec.stock_thickness_mm + 2, centered=(True, True, False)).translate((cutout["x"], cutout["y"], -1)))
        if before - part.val().Volume() < 0.01: raise ValueError("Cutout did not intersect the circular plate.")
    return part.translate((radius, radius, 0))


def _bent_profile(points_builder, width: float):
    profile = points_builder(cq.Workplane("XZ"))
    # XZ workplane extrudes toward -Y. Center the part around the origin.
    return profile.extrude(width).translate((0, width / 2, 0))


def _l_bracket(p: dict[str, float], width: float, height: float, radius: float, thickness: float):
    cx = radius + thickness
    cy = radius + thickness
    outer = radius + thickness
    inner = radius
    def draw(wp):
        return (wp.moveTo(0, cy + height).lineTo(0, cy)
            .threePointArc((cx - outer / math.sqrt(2), cy - outer / math.sqrt(2)), (cx, 0))
            .lineTo(cx + width, 0).lineTo(cx + width, thickness).lineTo(cx, thickness)
            .threePointArc((cx - inner / math.sqrt(2), cy - inner / math.sqrt(2)), (thickness, cy))
            .lineTo(thickness, cy + height).close())
    return _bent_profile(draw, p["width"])


def _u_channel(p: dict[str, float], thickness: float, radius: float):
    width, length, height = p["base_width"], p["length"], p["flange_height"]
    cx, cy = radius + thickness, radius + thickness
    outer, inner = radius + thickness, radius
    s2 = math.sqrt(2)
    def draw(wp):
        return (wp.moveTo(cx, 0).lineTo(width-cx, 0)
            .threePointArc((width-cx+outer/s2, cy-outer/s2), (width, cy))
            .lineTo(width, cy+height).lineTo(width-thickness, cy+height).lineTo(width-thickness, cy)
            .threePointArc((width-cx+inner/s2, cy-inner/s2), (width-cx, thickness))
            .lineTo(cx, thickness)
            .threePointArc((cx-inner/s2, cy-inner/s2), (thickness, cy))
            .lineTo(thickness, cy+height).lineTo(0, cy+height).lineTo(0, cy)
            .threePointArc((cx-outer/s2, cy-outer/s2), (cx, 0)).close())
    return _bent_profile(draw, length)


def _z_bracket(p: dict[str, float], thickness: float, radius: float):
    width, web, height = p["width"], p["base_length"], p["flange_height"]
    # Trace both offsets of a constant-thickness S-shaped sheet section.
    cx, cy = radius + thickness / 2, radius + thickness / 2
    outer, inner = radius + thickness, radius
    s2 = math.sqrt(2)
    right_x = web - cx
    def draw(wp):
        return (wp.moveTo(-thickness/2, cy+height).lineTo(-thickness/2, cy)
            .threePointArc((cx-outer/s2, cy-outer/s2), (cx, -thickness/2))
            .lineTo(right_x, -thickness/2)
            .threePointArc((right_x+inner/s2, -cy+inner/s2), (right_x+inner, -cy))
            .lineTo(right_x+inner, -cy-height).lineTo(right_x+outer, -cy-height).lineTo(right_x+outer, -cy)
            .threePointArc((right_x+outer/s2, -cy+outer/s2), (right_x, thickness/2))
            .lineTo(cx, thickness/2)
            .threePointArc((cx-inner/s2, cy-inner/s2), (thickness/2, cy))
            .lineTo(thickness/2, cy+height).close())
    return _bent_profile(draw, width)


def _apply_bent_web_cuts(part: cq.Workplane, spec: PartSpec, p: dict[str, float], *, web_width: float, web_length: float, z_bottom: float) -> cq.Workplane:
    """Cut features on the broad, horizontal web of a bent recipe.

    Feature coordinates are face-local: x and y start at the web's lower-left
    datum, while the CAD recipe centers the extrusion about world Y.
    """
    cuts: list[tuple[str, dict[str, float]]] = [("hole", x) for x in spec.holes]
    cuts += [("slot", x) for x in spec.slots]
    cuts += [("cutout", x) for x in spec.cutouts]
    for kind, item in cuts:
        x, y = item["x"], item["y"]
        size_x = item.get("diameter", item.get("length", 0))
        size_y = item.get("diameter", item.get("width", 0))
        if x - size_x / 2 < 0 or x + size_x / 2 > web_width or y - size_y / 2 < 0 or y + size_y / 2 > web_length:
            raise ValueError(f"{kind.title()} at x={x:g}, y={y:g} mm does not fit on the bent part's base web.")
        before = part.val().Volume()
        cutter_height = max(p.get("flange_height", 0), 3 * spec.stock_thickness_mm) + 4
        if kind == "hole":
            cutter = cq.Workplane("XY").center(x, y - web_length / 2).circle(item["diameter"] / 2).extrude(cutter_height).translate((0, 0, z_bottom - 2))
        elif kind == "slot":
            cutter = cq.Workplane("XY").center(x, y - web_length / 2).slot2D(item["length"], item["width"]).extrude(cutter_height).translate((0, 0, z_bottom - 2))
        else:
            cutter = cq.Workplane("XY").box(item["length"], item["width"], cutter_height, centered=(True, True, False)).translate((x, y - web_length / 2, z_bottom - 2))
        part = part.cut(cutter)
        if before - part.val().Volume() < 0.01:
            raise ValueError(f"The {kind} did not intersect the bent part's base web.")
    return part


BUILDERS = {TemplateId.RECT_PLATE: "flat", TemplateId.ROUND_PLATE: "flat", TemplateId.L_BRACKET: "l", TemplateId.U_CHANNEL: "u", TemplateId.Z_BRACKET: "z"}


def build_part(spec: PartSpec) -> tuple[cq.Workplane, list[InspectionFeature]]:
    validate_spec(spec)
    p = spec.parameters
    t = spec.stock_thickness_mm
    radius = p.get("inside_radius", R)
    kind = spec.template_id
    if kind == TemplateId.RECT_PLATE:
        part = _rect_plate(p, spec)
        dims = {"length": p["length"], "width": p["width"], "thickness": t}
        base = [InspectionFeature(id="face:top", kind="face", label="Top face", dimensions={"thickness": t})]
    elif kind == TemplateId.ROUND_PLATE:
        part = _round_plate(p, spec)
        dims = {"diameter": p["diameter"], "thickness": t}
        base = [InspectionFeature(id="face:top", kind="face", label="Top face", dimensions={"thickness": t})]
    elif kind == TemplateId.L_BRACKET:
        part = _l_bracket(p, p["base_length"], p["flange_height"], radius, t)
        part = _apply_bent_web_cuts(part, spec, p, web_width=p["base_length"], web_length=p["width"], z_bottom=0)
        dims = {"base length": p["base_length"], "width": p["width"], "flange height": p["flange_height"], "inside radius": radius, "thickness": t}
        base = [InspectionFeature(id="bend:1", kind="bend", label="90° bend", dimensions={"angle": "90°", "inside_radius": radius})]
    elif kind == TemplateId.U_CHANNEL:
        part = _u_channel(p, t, radius)
        part = _apply_bent_web_cuts(part, spec, p, web_width=p["base_width"], web_length=p["length"], z_bottom=0)
        dims = {"base width": p["base_width"], "length": p["length"], "flange height": p["flange_height"], "inside radius": radius, "thickness": t}
        base = [InspectionFeature(id="bend:1", kind="bend", label="Left 90° bend", dimensions={"angle": "90°", "inside_radius": radius}), InspectionFeature(id="bend:2", kind="bend", label="Right 90° bend", dimensions={"angle": "90°", "inside_radius": radius})]
    else:
        part = _z_bracket(p, t, radius)
        part = _apply_bent_web_cuts(part, spec, p, web_width=p["base_length"], web_length=p["width"], z_bottom=-t/2)
        dims = {"base length": p["base_length"], "width": p["width"], "flange height": p["flange_height"], "inside radius": radius, "thickness": t}
        base = [InspectionFeature(id="bend:1", kind="bend", label="Upper 90° bend", dimensions={"angle": "90°", "inside_radius": radius}), InspectionFeature(id="bend:2", kind="bend", label="Lower 90° bend", dimensions={"angle": "90°", "inside_radius": radius})]
    features = [InspectionFeature(id="overall", kind="overall", label="Overall size", dimensions=dims), *base]
    for feature in features:
        if feature.kind == "overall":
            feature.point_mm = [part.val().BoundingBox().center.x, part.val().BoundingBox().center.y, part.val().BoundingBox().center.z]
        elif feature.kind == "face":
            feature.point_mm = [0, 0, t]
        elif feature.kind == "bend" and kind == TemplateId.L_BRACKET:
            feature.point_mm = [radius + t, 0, radius + t]
        elif feature.kind == "bend" and kind == TemplateId.U_CHANNEL:
            x = (radius + t) if feature.id == "bend:1" else p["base_width"] - (radius + t)
            feature.point_mm = [x, 0, radius + t]
        elif feature.kind == "bend" and kind == TemplateId.Z_BRACKET:
            x = radius + t / 2 if feature.id == "bend:1" else p["base_length"] - (radius + t / 2)
            z = radius + t / 2 if feature.id == "bend:1" else -(radius + t / 2)
            feature.point_mm = [x, 0, z]
    for i, hole in enumerate(spec.holes, 1):
        x0 = p.get("diameter", p.get("length", p.get("base_length", 100))) / 2 if kind == TemplateId.ROUND_PLATE else 0
        y0 = p.get("diameter", p.get("width", p.get("base_width", 70))) / 2 if kind == TemplateId.ROUND_PLATE else 0
        features.append(InspectionFeature(id=f"hole:{i}", kind="hole", label=f"Hole {i}", dimensions=hole, point_mm=[hole["x"] + x0, hole["y"] + y0, t]))
    for i, slot in enumerate(spec.slots, 1):
        x0 = p.get("diameter", p.get("length", p.get("base_length", 100))) / 2 if kind == TemplateId.ROUND_PLATE else 0
        y0 = p.get("diameter", p.get("width", p.get("base_width", 70))) / 2 if kind == TemplateId.ROUND_PLATE else 0
        features.append(InspectionFeature(id=f"slot:{i}", kind="slot", label=f"Slot {i}", dimensions=slot, point_mm=[slot["x"] + x0, slot["y"] + y0, t]))
    for i, cutout in enumerate(spec.cutouts, 1):
        x0 = p.get("diameter", p.get("length", p.get("base_length", 100))) / 2 if kind == TemplateId.ROUND_PLATE else 0
        y0 = p.get("diameter", p.get("width", p.get("base_width", 70))) / 2 if kind == TemplateId.ROUND_PLATE else 0
        features.append(InspectionFeature(id=f"cutout:{i}", kind="cutout", label=f"Cutout {i}", dimensions=cutout, point_mm=[cutout["x"] + x0, cutout["y"] + y0, t]))
    return part, features


def _findings(spec: PartSpec, part: cq.Workplane) -> list[Finding]:
    findings = [Finding(id="geom", severity="pass", title="Solid geometry is valid", detail="The recipe generated a single solid from the current specification.")]
    profile = _profile("sendcutsend-5052-h32-0.063in")
    findings.extend([
        Finding(id="supplier-profile", severity="unknown", title="Supplier profile needs review", detail=profile["unverified"][0]),
        Finding(id="evidence", severity="warning", title="Experimental manufacturing status", detail="Generated files are for evaluation. Supplier acceptance and a measured physical sample are not yet recorded."),
    ])
    dims = spec.parameters
    for i, hole in enumerate(spec.holes, 1):
        if hole.get("diameter", 0) < spec.stock_thickness_mm * .5:
            findings.append(Finding(id=f"hole-small-{i}", severity="error", title=f"Hole {i} may be too small", detail="This opening is smaller than half the stock thickness; check the supplier limit.", feature_id=f"hole:{i}"))
    return findings


def export_build(spec: PartSpec) -> BuildResult:
    build_id = uuid4().hex
    folder = DATA_DIR / "builds" / build_id
    folder.mkdir(parents=True, exist_ok=True)
    try:
        part, features = build_part(spec)
        solid = part.val()
        if not solid.isValid() or len(solid.Solids()) != 1:
            raise ValueError("Expected one valid solid.")
        glb_path = folder / "model.glb"
        stl_path = folder / "preview.stl"
        cq.exporters.export(part, str(stl_path), cq.exporters.ExportTypes.STL, tolerance=0.05, angularTolerance=0.15)
        import trimesh
        mesh = trimesh.load_mesh(stl_path, process=True)
        mesh.export(glb_path, file_type="glb")
        stl_path.unlink()
        if spec.template_id in {TemplateId.RECT_PLATE, TemplateId.ROUND_PLATE}:
            dxf_path = folder / "part.dxf"
            wp = cq.Workplane("XY")
            wires = part.faces(">Z").wires().vals()
            for wire in wires:
                wp = wp.add(wire)
            cq.exporters.exportDXF(wp, str(dxf_path), doc_units=4)
            cad_name = "part.dxf"
        else:
            cq.exporters.export(part, str(folder / "part.step"), cq.exporters.ExportTypes.STEP, outputUnit="MM")
            cad_name = "part.step"
        (folder / "specification.json").write_text(spec.model_dump_json(indent=2))
        findings = _findings(spec, part)
        report = {"revision": spec.revision, "geometry_status": "valid", "supplier_status": "incomplete", "evidence_status": "experimental", "findings": [f.model_dump() for f in findings]}
        (folder / "validation.json").write_text(json.dumps(report, indent=2))
        (folder / "inspection.json").write_text(json.dumps([f.model_dump() for f in features], indent=2))
        pdf = canvas.Canvas(str(folder / "dimensions.pdf"), pagesize=letter)
        pdf.setFont("Helvetica-Bold", 18)
        pdf.drawString(54, 740, f"Foldspec · {spec.template_id.value.replace('_', ' ').title()}")
        pdf.setFont("Helvetica", 10)
        pdf.drawString(54, 718, f"Revision {spec.revision} · Experimental · All dimensions in mm")
        y = 680
        for feature in features:
            if feature.id == "overall":
                pdf.setFont("Helvetica-Bold", 11)
                pdf.drawString(54, y, "Overall dimensions")
                y -= 20
                pdf.setFont("Helvetica", 10)
                for name, value in feature.dimensions.items():
                    pdf.drawString(66, y, f"{name}: {value}")
                    y -= 16
        y -= 10
        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawString(54, y, "Manufacturing status")
        pdf.setFont("Helvetica", 9)
        pdf.drawString(54, y-17, "Geometry generated. Supplier rules and physical fit require independent review.")
        pdf.drawString(54, y-34, "This prototype package is experimental; it is not a validated production release.")
        pdf.save()
        instructions = "Foldspec prototype package. Inspect the attached validation report. This package is experimental and has not been validated for production. Upload files to a supplier only after reviewing current supplier rules and the part geometry."
        (folder / "README.txt").write_text(instructions + "\n")
        artifact_names = [cad_name, "dimensions.pdf", "specification.json", "validation.json", "inspection.json", "README.txt"]
        manifest = {"spec_revision": spec.revision, "template": spec.template_id.value, "recipe_version": "0.1.0", "generator_version": "foldspec-cad/0.1.0", "supplier_profile": _profile("sendcutsend-5052-h32-0.063in"), "evidence_status": "experimental", "files": [{"name": name, "sha256": hashlib.sha256((folder / name).read_bytes()).hexdigest()} for name in artifact_names]}
        (folder / "manifest.json").write_text(json.dumps(manifest, indent=2))
        zip_path = folder / "foldspec-package.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in folder.iterdir():
                if path != zip_path:
                    archive.write(path, path.name)
        bounds = solid.BoundingBox()
        return BuildResult(revision=spec.revision, geometry_status="valid", supplier_status="incomplete", evidence_status="experimental", findings=findings, features=features, bounds_mm={"x": bounds.xlen, "y": bounds.ylen, "z": bounds.zlen}, glb_url=f"/api/artifacts/{build_id}/model.glb", export_url=f"/api/artifacts/{build_id}/foldspec-package.zip")
    except Exception as exc:
        shutil.rmtree(folder, ignore_errors=True)
        return BuildResult(revision=spec.revision, geometry_status="invalid", supplier_status="incomplete", evidence_status="experimental", findings=[Finding(id="cad-error", severity="error", title="Could not build this model", detail=str(exc))], glb_url="", export_url="")
