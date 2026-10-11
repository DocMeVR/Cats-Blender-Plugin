# MIT License

"""Smoke test for Cats in Blender 5.2.

Loads Cats, draws every Cats panel with a layout that checks icons, properties and operators, and runs the main
tools on a generated test avatar or on a model of your own.

Run it from the repository root:

    blender --background --factory-startup --python-exit-code 1 --python tests/smoke_test.py
    blender --background --factory-startup --python-exit-code 1 --python tests/smoke_test.py -- --model path/to/avatar.fbx

Options after "--":
    --zip PATH     Install this extension zip instead of loading Cats from the source folder. Set the environment
                   variable BLENDER_USER_RESOURCES to an empty folder first, so your own Blender setup is not touched.
    --model PATH   Import this model (fbx, pmx, vrm, ...) instead of generating a test avatar.
    --out DIR      Folder for the exported FBX. Defaults to a temporary folder.

Some tools need a 3D Viewport. In background mode those are skipped. Run without --background to test them too.
"""

import os
import sys
import time
import tempfile
import argparse
import traceback
import contextlib
import importlib.util

import bpy
import addon_utils

SOURCE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXTENSION_MODULE = 'bl_ext.user_default.cats_blender_plugin'

parser = argparse.ArgumentParser()
parser.add_argument('--zip')
parser.add_argument('--model')
parser.add_argument('--out')
args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
out_dir = args.out or tempfile.mkdtemp(prefix='cats_smoke_')
os.makedirs(out_dir, exist_ok=True)

results = []
captured_errors = []
cats = None


# ---------------------------------------------------------------------------------------------------------------------
# Helpers

def view3d_override():
    if bpy.app.background:
        return contextlib.nullcontext()
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'VIEW_3D':
                region = next(r for r in area.regions if r.type == 'WINDOW')
                return bpy.context.temp_override(window=window, screen=window.screen, area=area, region=region)
    return contextlib.nullcontext()


def step(name, func, needs_view3d=False):
    if needs_view3d and bpy.app.background:
        results.append((name, 'SKIPPED', 'needs a 3D Viewport'))
        return
    del captured_errors[:]
    start = time.time()
    status, detail = 'OK', ''
    try:
        with view3d_override():
            result = func()
        if isinstance(result, set) and 'FINISHED' not in result:
            status, detail = 'FAILED', str(result)
    except Exception as e:
        status = 'FAILED'
        detail = ' / '.join(''.join(traceback.format_exception(e)).strip().splitlines()[-3:])
    if status == 'OK' and captured_errors:
        status, detail = 'FAILED', captured_errors[0][:300]
    results.append((name, status, detail))
    print(f'### {status:7s} {time.time() - start:6.1f}s  {name}  {detail}')
    sys.stdout.flush()


def ensure_object_mode():
    obj = bpy.context.view_layer.objects.active
    if obj and obj.mode != 'OBJECT':
        with view3d_override():
            bpy.ops.object.mode_set(mode='OBJECT')


def set_active(obj):
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def armature():
    return next(o for o in bpy.data.objects if o.type == 'ARMATURE')


def meshes():
    return [o for o in bpy.data.objects if o.type == 'MESH']


def body_mesh():
    with_keys = [m for m in meshes() if m.data.shape_keys and len(m.data.shape_keys.key_blocks) > 3]
    return max(with_keys or meshes(), key=lambda m: len(m.data.vertices))


def find_shape_key(mesh, *names):
    if not mesh.data.shape_keys:
        return None
    keys = [k.name for k in mesh.data.shape_keys.key_blocks]
    for name in names:
        for key in keys:
            if key.lower() == name.lower():
                return key
    return None


# ---------------------------------------------------------------------------------------------------------------------
# Loading Cats

def load_from_source():
    spec = importlib.util.spec_from_file_location('cats_blender_plugin', os.path.join(SOURCE_DIR, '__init__.py'),
                                                  submodule_search_locations=[SOURCE_DIR])
    module = importlib.util.module_from_spec(spec)
    sys.modules['cats_blender_plugin'] = module
    spec.loader.exec_module(module)
    module.register()
    return module


def load_from_zip(path):
    result = bpy.ops.extensions.package_install_files(filepath=path, repo='user_default', enable_on_install=True)
    if 'FINISHED' not in result or not addon_utils.check(EXTENSION_MODULE)[1]:
        raise RuntimeError('Installing ' + path + ' failed')
    return sys.modules[EXTENSION_MODULE]


def capture_cats_errors():
    common = sys.modules[cats.__name__ + '.tools.common']

    def show_error(scale, error_list, override_header=False):
        message = error_list if isinstance(error_list, str) else ' | '.join(map(str, error_list))
        captured_errors.append(message)
        print('    Cats error:', message)

    common.show_error = show_error


# ---------------------------------------------------------------------------------------------------------------------
# Drawing all panels with a layout that validates what is drawn

ICONS = {i.identifier for i in bpy.types.UILayout.bl_rna.functions['label'].parameters['icon'].enum_items}
PROPERTY_FUNCTIONS = {'prop', 'prop_search', 'prop_enum', 'prop_menu_enum', 'props_enum', 'prop_tabs_enum'}


class OperatorProperties:
    pass


class CheckingLayout:
    def __init__(self, owner, problems):
        self.__dict__['_owner'] = owner
        self.__dict__['_problems'] = problems

    def __setattr__(self, key, value):
        self.__dict__[key] = value

    def __getattr__(self, function_name):
        owner, problems = self._owner, self._problems

        def function(*f_args, **f_kwargs):
            icon = f_kwargs.get('icon')
            if isinstance(icon, str) and icon and icon not in ICONS:
                problems.append(f'{owner}: unknown icon {icon!r}')
            if function_name in PROPERTY_FUNCTIONS and len(f_args) >= 2:
                data, prop = f_args[0], f_args[1]
                if data is not None and hasattr(data, 'bl_rna') and prop not in data.bl_rna.properties:
                    problems.append(f'{owner}: missing property {prop!r} on {data.bl_rna.identifier}')
            if function_name in ('operator', 'operator_menu_enum'):
                idname = f_args[0] if f_args else f_kwargs.get('operator')
                category, _, name = idname.partition('.')
                try:
                    getattr(getattr(bpy.ops, category), name).get_rna_type()
                except (AttributeError, KeyError):
                    problems.append(f'{owner}: missing operator {idname!r}')
                return OperatorProperties()
            return CheckingLayout(owner, problems)

        return function


def draw_all_panels():
    def subclasses(cls):
        for sub in cls.__subclasses__():
            yield sub
            yield from subclasses(sub)

    prefixes = (cats.__name__, 'mmd_tools_local')
    classes = [c for base in (bpy.types.Panel, bpy.types.Menu) for c in subclasses(base)
               if c.__module__.startswith(prefixes) and getattr(c, 'is_registered', False)]
    # Menus are only opened from their panels, which need an active object
    if bpy.context.active_object is None:
        classes = [c for c in classes if not issubclass(c, bpy.types.Menu)]

    problems = []
    for cls in classes:
        fake_self = type('PanelInstance', (), {
            'layout': CheckingLayout(cls.__name__, problems),
            '__getattr__': lambda s, n, c=cls: getattr(c, n).__get__(s) if callable(getattr(c, n)) else getattr(c, n),
        })()
        try:
            if hasattr(cls, 'poll') and not cls.poll(bpy.context):
                continue
            if hasattr(cls, 'draw_header'):
                cls.draw_header(fake_self, bpy.context)
            cls.draw(fake_self, bpy.context)
        except Exception as e:
            problems.append(f'{cls.__name__}: {type(e).__name__}: {e}')
    if not classes:
        problems.append('no Cats panels are registered')
    if problems:
        raise RuntimeError('; '.join(problems[:8]))
    return {'FINISHED'}


# ---------------------------------------------------------------------------------------------------------------------
# Test avatar

def build_test_avatar():
    """A small humanoid with eyes, an MMD style naming mix and the shape keys Cats needs for visemes and eye tracking"""
    bpy.ops.object.armature_add(enter_editmode=True)
    arm = bpy.context.object
    arm.name = 'Armature'
    edit_bones = arm.data.edit_bones
    edit_bones.remove(edit_bones[0])

    def bone(name, head, tail, parent=None):
        b = edit_bones.new(name)
        b.head, b.tail = head, tail
        if parent:
            b.parent = edit_bones[parent]
        return b

    bone('Hips', (0, 0, 1.0), (0, 0, 1.1))
    bone('Spine', (0, 0, 1.1), (0, 0, 1.25), 'Hips')
    bone('Chest', (0, 0, 1.25), (0, 0, 1.4), 'Spine')
    bone('Neck', (0, 0, 1.4), (0, 0, 1.5), 'Chest')
    bone('Head', (0, 0, 1.5), (0, 0, 1.75), 'Neck')
    bone('Eye_L', (0.03, -0.08, 1.62), (0.03, -0.08, 1.66), 'Head')
    bone('Eye_R', (-0.03, -0.08, 1.62), (-0.03, -0.08, 1.66), 'Head')
    for side, x in (('L', 1), ('R', -1)):
        bone(f'Shoulder_{side}', (0.03 * x, 0, 1.38), (0.12 * x, 0, 1.38), 'Chest')
        bone(f'UpperArm_{side}', (0.12 * x, 0, 1.38), (0.35 * x, 0, 1.38), f'Shoulder_{side}')
        bone(f'LowerArm_{side}', (0.35 * x, 0, 1.38), (0.58 * x, 0, 1.38), f'UpperArm_{side}')
        bone(f'Hand_{side}', (0.58 * x, 0, 1.38), (0.66 * x, 0, 1.38), f'LowerArm_{side}')
        bone(f'UpperLeg_{side}', (0.1 * x, 0, 1.0), (0.1 * x, 0, 0.55), 'Hips')
        bone(f'LowerLeg_{side}', (0.1 * x, 0, 0.55), (0.1 * x, 0, 0.1), f'UpperLeg_{side}')
        bone(f'Foot_{side}', (0.1 * x, 0, 0.1), (0.1 * x, -0.1, 0.02), f'LowerLeg_{side}')
        bone(f'Toe_{side}', (0.1 * x, -0.1, 0.02), (0.1 * x, -0.15, 0.02), f'Foot_{side}')
    bone('Skirt_Unused', (0, -0.1, 1.0), (0, -0.1, 0.8), 'Hips')
    # Two similar hair chains for bone merging
    for strand, x in (('A', 0.04), ('B', -0.04)):
        for i in range(1, 5):
            top = 1.72 - (i - 1) * 0.1
            bone(f'Hair{strand}_{i}', (x, 0.1, top), (x, 0.1, top - 0.1), 'Head' if i == 1 else f'Hair{strand}_{i - 1}')

    centers = {b.name: ((b.head + b.tail) / 2, b.length) for b in edit_bones}
    bpy.ops.object.mode_set(mode='OBJECT')

    # One cube per bone, weighted to that bone
    parts = []
    for name, (center, length) in centers.items():
        if name == 'Skirt_Unused' or name.startswith('Hair'):
            continue
        size = 0.04 if name.startswith('Eye') else max(0.05, length * 0.6)
        bpy.ops.mesh.primitive_cube_add(size=size, location=center)
        part = bpy.context.object
        part.vertex_groups.new(name=name).add(list(range(len(part.data.vertices))), 1.0, 'REPLACE')
        parts.append(part)
    for part in parts:
        part.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    body = bpy.context.object
    body.name = 'Body'
    body.parent = arm
    body.modifiers.new('Armature', 'ARMATURE').object = arm

    material = bpy.data.materials.new('Skin')
    body.data.materials.append(material)

    # Shape keys moving the head and eye vertices
    head_group = body.vertex_groups['Head'].index
    eye_groups = {body.vertex_groups['Eye_L'].index, body.vertex_groups['Eye_R'].index}
    head_verts = [v.index for v in body.data.vertices if any(g.group == head_group for g in v.groups)]
    eye_verts = [v.index for v in body.data.vertices if any(g.group in eye_groups for g in v.groups)]
    body.shape_key_add(name='Basis')
    for key_name, offset, verts in (('vrc.v_aa', (0, 0, -0.01), head_verts), ('vrc.v_oh', (0, -0.01, 0), head_verts),
                                    ('vrc.v_ch', (0.01, 0, 0), head_verts), ('Blink_L', (0, 0, -0.005), eye_verts),
                                    ('Blink_R', (0, 0, -0.005), eye_verts), ('Unused', (0, 0, 0), head_verts)):
        key = body.shape_key_add(name=key_name, from_mix=False)
        for index in verts:
            co = key.data[index].co
            key.data[index].co = (co[0] + offset[0], co[1] + offset[1], co[2] + offset[2])

    # Hair meshes for join/separate, weighted along the hair chains
    hair_material = bpy.data.materials.new('Hair')
    for strand, x in (('A', 0.04), ('B', -0.04)):
        bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=0.02, depth=0.4, location=(x, 0.1, 1.52))
        bpy.ops.object.transform_apply(location=True)
        hair = bpy.context.object
        hair.name = 'Hair' + strand
        for i in range(1, 5):
            top = 1.72 - (i - 1) * 0.1
            hair.vertex_groups.new(name=f'Hair{strand}_{i}').add(
                [v.index for v in hair.data.vertices if top - 0.1 <= v.co.z <= top + 0.001], 1.0, 'REPLACE')
        hair.parent = arm
        hair.modifiers.new('Armature', 'ARMATURE').object = arm
        hair.data.materials.append(hair_material)
    return {'FINISHED'}


# ---------------------------------------------------------------------------------------------------------------------
# Tests

def run():
    global cats
    print('Blender', bpy.app.version_string, '| Python', sys.version.split()[0],
          '| background' if bpy.app.background else '| with UI')

    try:
        cats = load_from_zip(args.zip) if args.zip else load_from_source()
        results.append(('load Cats', 'OK', cats.__name__))
    except Exception as e:
        results.append(('load Cats', 'FAILED', f'{type(e).__name__}: {e}'))
        traceback.print_exc()
        return
    capture_cats_errors()
    scene = bpy.context.scene

    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj)
    step('draw panels, empty scene', draw_all_panels)

    if args.model:
        step('import model', lambda: bpy.ops.cats_importer.import_any_model(
            directory=os.path.dirname(args.model), files=[{'name': os.path.basename(args.model)}]))
    else:
        step('build test avatar', build_test_avatar)
    if not any(o.type == 'ARMATURE' for o in bpy.data.objects):
        results.append(('find armature', 'FAILED', 'nothing was imported'))
        return
    scene.armature = armature().name
    step('draw panels, model loaded', draw_all_panels)

    ensure_object_mode()
    step('fix model', lambda: bpy.ops.cats_armature.fix())
    ensure_object_mode()
    step('draw panels, model fixed', draw_all_panels)

    # Pose mode tools
    arm = armature()
    set_active(arm)
    step('start pose mode', lambda: bpy.ops.cats_manual.start_pose_mode())
    step('draw panels, pose mode', draw_all_panels)

    def bend_and_save_pose():
        pose_bone = arm.pose.bones.get('Left arm') or arm.pose.bones[len(arm.pose.bones) // 2]
        pose_bone.rotation_mode = 'XYZ'
        pose_bone.rotation_euler[0] = 0.5
        scene.pose_to_shapekey_name = 'SmokeTestPose'
        bpy.ops.cats_manual.pose_name_popup('EXEC_DEFAULT')
        if not any(m.data.shape_keys and 'SmokeTestPose' in m.data.shape_keys.key_blocks for m in meshes()):
            raise RuntimeError('no shape key was created from the pose')
        return {'FINISHED'}

    step('pose to shape key', bend_and_save_pose)
    step('stop pose mode', lambda: bpy.ops.cats_manual.stop_pose_mode(), needs_view3d=True)
    ensure_object_mode()
    set_active(arm)
    step('start pose mode, keep pose', lambda: bpy.ops.cats_manual.start_pose_mode_no_reset())
    step('apply pose as rest pose', lambda: bpy.ops.cats_manual.pose_to_rest(), needs_view3d=True)
    step('stop pose mode, keep pose', lambda: bpy.ops.cats_manual.stop_pose_mode_no_reset(), needs_view3d=True)
    ensure_object_mode()

    step('join meshes', lambda: bpy.ops.cats_manual.join_meshes())
    ensure_object_mode()
    body = body_mesh()

    # Visemes
    keys = [find_shape_key(body, 'vrc.v_aa', 'あ'), find_shape_key(body, 'vrc.v_oh', 'お'),
            find_shape_key(body, 'vrc.v_ch', 'い')]
    if all(keys):
        scene.mesh_name_viseme = body.name
        scene.mouth_a, scene.mouth_o, scene.mouth_ch = keys
        step('create visemes', lambda: bpy.ops.cats_viseme.create())
    else:
        results.append(('create visemes', 'SKIPPED', 'model has no a/o/ch shape keys'))
    ensure_object_mode()

    # Eye tracking
    arm = armature()
    eye_left = next((b.name for b in arm.data.bones if b.name.lower() in ('eye_l', 'lefteye', 'left eye')), None)
    eye_right = next((b.name for b in arm.data.bones if b.name.lower() in ('eye_r', 'righteye', 'right eye')), None)
    if eye_left and eye_right and 'Head' in arm.data.bones:
        scene.mesh_name_eye = body.name
        scene.head = 'Head'
        scene.eye_left, scene.eye_right = eye_left, eye_right
        blink_left = find_shape_key(body, 'Blink_L', 'Blink left', 'vrc.blink_left')
        blink_right = find_shape_key(body, 'Blink_R', 'Blink right', 'vrc.blink_right')
        scene.disable_eye_blinking = not (blink_left and blink_right)
        if blink_left and blink_right:
            scene.wink_left, scene.wink_right = blink_left, blink_right
            scene.lowerlid_left, scene.lowerlid_right = blink_left, blink_right
        scene.disable_eye_movement = False
        for mode in [i.identifier for i in bpy.types.Scene.bl_rna.properties['eye_tracking_mode'].enum_items]:
            scene.eye_tracking_mode = mode
            ensure_object_mode()
            step(f'create eye tracking ({mode})', lambda: bpy.ops.cats_eyes.create_eye_tracking())
            ensure_object_mode()
        step('draw panels, eye tracking', draw_all_panels)
    else:
        results.append(('create eye tracking', 'SKIPPED', 'model has no eye bones'))

    # Optimization
    ensure_object_mode()
    def merge_bones():
        bpy.ops.cats_bonemerge.load_bones()
        root_bones = sys.modules[cats.__name__ + '.globs'].root_bones
        if not root_bones:
            raise RuntimeError('no bone chains were found to merge')
        scene.merge_bone = next(iter(root_bones))
        scene.merge_mesh = body_mesh().name
        scene.merge_ratio = 50
        return bpy.ops.cats_bonemerge.merge_bones()

    step('merge bones', merge_bones)
    ensure_object_mode()
    step('combine materials', lambda: bpy.ops.cats_material.combine_mats())
    ensure_object_mode()

    # Shape keys
    body = body_mesh()
    set_active(body)
    if body.data.shape_keys and len(body.data.shape_keys.key_blocks) > 2:
        body.active_shape_key_index = len(body.data.shape_keys.key_blocks) - 1
        step('shape key to basis', lambda: bpy.ops.cats_shapekey.shape_key_to_basis())
        ensure_object_mode()
        set_active(body)
        step('prune shape keys', lambda: bpy.ops.cats_shapekey.shape_key_prune())
        ensure_object_mode()

    # Mesh and armature tools
    for name, op, obj_getter in (
            ('remove zero weight vertex groups', bpy.ops.cats_manual.remove_zero_weight_groups, body_mesh),
            ('remove zero weight bones', bpy.ops.cats_manual.remove_zero_weight_bones, armature),
            ('recalculate normals', bpy.ops.cats_manual.recalculate_normals, body_mesh),
            ('flip normals', bpy.ops.cats_manual.flip_normals, body_mesh),
            ('remove doubles', bpy.ops.cats_manual.remove_doubles, body_mesh),
            ('apply transformations', bpy.ops.cats_manual.apply_transformations, armature),
            ('remove constraints', bpy.ops.cats_manual.remove_constraints, armature),
            ('optimize static shape keys', bpy.ops.cats_manual.optimize_static_shapekeys, body_mesh),
            ('separate by materials', bpy.ops.cats_manual.separate_by_materials, body_mesh),
            ('join meshes again', bpy.ops.cats_manual.join_meshes, armature),
            ('separate by shape keys', bpy.ops.cats_manual.separate_by_shape_keys, body_mesh),
            ('join meshes a third time', bpy.ops.cats_manual.join_meshes, armature)):
        ensure_object_mode()
        set_active(obj_getter())
        step(name, lambda: op())
    ensure_object_mode()

    def merge_weights():
        arm = armature()
        set_active(arm)
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.armature.select_all(action='DESELECT')
        target = next(b for b in arm.data.edit_bones if b.parent and b.parent.parent and b.children)
        target.select = target.select_head = target.select_tail = True
        return bpy.ops.cats_manual.merge_weights()

    step('merge weights to parent', merge_weights)
    ensure_object_mode()

    step('refresh root bone list', lambda: bpy.ops.cats_root.refresh_root_list())

    # Custom model tools
    def attach_mesh():
        bpy.ops.mesh.primitive_cube_add(size=0.1)
        cube = bpy.context.object
        cube.name = 'SmokeTestCube'
        scene.merge_armature_into = armature().name
        scene.attach_mesh = cube.name
        scene.attach_to_bone = 'Head' if 'Head' in armature().data.bones else armature().data.bones[0].name
        return bpy.ops.cats_custom.attach_mesh()

    ensure_object_mode()
    step('attach mesh', attach_mesh)
    ensure_object_mode()

    def merge_armatures():
        base = armature()
        set_active(base)
        bpy.ops.object.duplicate()
        outfit = bpy.context.object
        outfit.name = 'SmokeTestOutfit'
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.05)
        outfit_mesh = bpy.context.object
        outfit_mesh.parent = outfit
        outfit_mesh.modifiers.new('Armature', 'ARMATURE').object = outfit
        group_name = 'Hips' if 'Hips' in outfit.data.bones else outfit.data.bones[0].name
        outfit_mesh.vertex_groups.new(name=group_name).add(list(range(len(outfit_mesh.data.vertices))), 1.0, 'REPLACE')
        ensure_object_mode()
        scene.merge_armature_into = base.name
        scene.merge_armature = outfit.name
        return bpy.ops.cats_custom.merge_armatures()

    step('merge armatures', merge_armatures)
    ensure_object_mode()
    step('draw panels, after merging', draw_all_panels)

    # Export and import the result again
    fbx_path = os.path.join(out_dir, 'cats_smoke_test.fbx')
    step('export model', lambda: bpy.ops.cats_importer.export_model(action='NO_CHECK', filepath=fbx_path))

    def reimport():
        if not os.path.isfile(fbx_path):
            raise RuntimeError('the FBX file was not written')
        for obj in list(bpy.data.objects):
            bpy.data.objects.remove(obj)
        result = bpy.ops.import_scene.fbx(filepath=fbx_path)
        if not any(o.type == 'ARMATURE' for o in bpy.data.objects):
            raise RuntimeError('the exported FBX has no armature')
        return result

    step('import exported FBX', reimport)

    # Disabling and enabling again
    def operator_registered(idname):
        category, _, name = idname.partition('.')
        try:
            getattr(getattr(bpy.ops, category), name).get_rna_type()
            return True
        except KeyError:
            return False

    if args.zip:
        def disable_enable():
            bpy.ops.preferences.addon_disable(module=EXTENSION_MODULE)
            if hasattr(bpy.types.Scene, 'armature') or operator_registered('cats_armature.fix'):
                raise RuntimeError('Cats left properties or operators behind after disabling')
            bpy.ops.preferences.addon_enable(module=EXTENSION_MODULE)
            if not hasattr(bpy.types.Scene, 'armature'):
                raise RuntimeError('Cats did not register again')
            return {'FINISHED'}
    else:
        def disable_enable():
            cats.unregister()
            if hasattr(bpy.types.Scene, 'armature'):
                raise RuntimeError('Cats left scene properties behind after unregistering')
            cats.register()
            return {'FINISHED'}

    step('disable and enable again', disable_enable)


try:
    run()
except Exception:
    traceback.print_exc()
    results.append(('test run', 'FAILED', 'unexpected error, see above'))

print('\n======== Cats smoke test summary ========')
for name, status, detail in results:
    print(f'{status:7s}  {name}  {detail[:300]}')
failed = [r for r in results if r[1] == 'FAILED']
print(f'{len(results) - len(failed)} of {len(results)} steps passed or were skipped')
sys.stdout.flush()
# Exit without running Blender's cleanup, threads started by the updater could otherwise keep Blender open
os._exit(1 if failed else 0)
