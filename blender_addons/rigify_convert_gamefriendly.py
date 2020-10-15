import bpy
from mathutils import Vector

from bpy.props import BoolProperty

bl_info = {
    "name": "Rigify - Make Game Friendly",
    "author": "Paolo Acampora",
    "version": (1, 0, 3),
    "blender": (2, 80, 0),
    "location": "Armature Context Menu (right click, armature edit mode)",
    "description": "Brings the DEF- bones of rigify 0.5 rigs into a single, game friendly hierarchy",
    "category": "Rigging",
    }


def copy_bone_constraints(bone_a, bone_b):
    """Copy all bone constraints from bone_A to bone_b and sets their writable attributes.
       Doesn't delete constraints that already exist
    """
    for constr_a in bone_a.constraints:
        constr_b = bone_b.constraints.new(constr_a.type)

        for c_attr in dir(constr_b):
            if c_attr.startswith("_"):
                continue
            try:
                setattr(constr_b, c_attr, getattr(constr_a, c_attr))
            except AttributeError:
                continue


def copy_bone(ob, bone_name, assign_name='', constraints=False, deform_bone='SAME'):
    """ Makes a copy of the given bone in the given armature object.
        Returns the resulting bone's name.

        NOTE: taken from rigify module utils.py, added the contraints option and stripped the part about rna properties
    """
    if bone_name not in ob.data.edit_bones:
        raise Exception("copy_bone(): bone '%s' not found, cannot copy it" % bone_name)

    if assign_name == '':
        assign_name = bone_name
    # Copy the edit bone
    edit_bone_1 = ob.data.edit_bones[bone_name]
    edit_bone_2 = ob.data.edit_bones.new(assign_name)

    bone_name_1 = bone_name
    bone_name_2 = edit_bone_2.name

    edit_bone_2.parent = edit_bone_1.parent
    edit_bone_2.use_connect = edit_bone_1.use_connect

    # Copy edit bone attributes
    edit_bone_2.layers = list(edit_bone_1.layers)

    edit_bone_2.head = Vector(edit_bone_1.head)
    edit_bone_2.tail = Vector(edit_bone_1.tail)
    edit_bone_2.roll = edit_bone_1.roll

    edit_bone_2.use_inherit_rotation = edit_bone_1.use_inherit_rotation
    edit_bone_2.use_inherit_scale = edit_bone_1.use_inherit_scale
    edit_bone_2.use_local_location = edit_bone_1.use_local_location

    if deform_bone == 'SAME':
        edit_bone_2.use_deform = edit_bone_1.use_deform
    else:
        edit_bone_2.use_deform = deform_bone
    edit_bone_2.bbone_segments = edit_bone_1.bbone_segments
    edit_bone_2.bbone_custom_handle_start = edit_bone_1.bbone_custom_handle_start
    edit_bone_2.bbone_custom_handle_end = edit_bone_1.bbone_custom_handle_end

    # ITD- bones go to MCH layer
    edit_bone_2.layers[30] = True
    edit_bone_2.layers[31] = False
    for i in range(30):
        edit_bone_2.layers[i] = False

    ob.update_from_editmode()

    # Get the pose bones
    pose_bone_1 = ob.pose.bones[bone_name_1]
    pose_bone_2 = ob.pose.bones[bone_name_2]

    # Copy pose bone attributes
    pose_bone_2.rotation_mode = pose_bone_1.rotation_mode
    pose_bone_2.rotation_axis_angle = tuple(pose_bone_1.rotation_axis_angle)
    pose_bone_2.rotation_euler = tuple(pose_bone_1.rotation_euler)
    pose_bone_2.rotation_quaternion = tuple(pose_bone_1.rotation_quaternion)

    pose_bone_2.lock_location = tuple(pose_bone_1.lock_location)
    pose_bone_2.lock_scale = tuple(pose_bone_1.lock_scale)
    pose_bone_2.lock_rotation = tuple(pose_bone_1.lock_rotation)
    pose_bone_2.lock_rotation_w = pose_bone_1.lock_rotation_w
    pose_bone_2.lock_rotations_4d = pose_bone_1.lock_rotations_4d

    if constraints:
        copy_bone_constraints(pose_bone_1, pose_bone_2)

    return bone_name_2


def remove_bone_constraints(pbone):
    for constr in pbone.constraints:
        pbone.constraints.remove(constr)


def remove_all_bone_constraints(ob):
    for pbone in ob.pose.bones:
        remove_bone_constraints(pbone)


def get_armature_bone(ob, bone_name):
    """Return the Armature Bone with given bone_name, None if not found"""
    return ob.data.bones.get(bone_name, None)


def get_edit_bone(ob, bone_name):
    """Return the Edit Bone with given bone name, None if not found"""
    return ob.data.edit_bones.get(bone_name, None)


def is_def_bone(ob, bone_name):
    """Return True if the bone with given name is a deforming bone,
       False if it isn't, None if the bone is not found"""
    bone = get_armature_bone(ob, bone_name)

    if not bone:
        return

    return bone.use_deform


def find_def_parent(ob, org_bone):
    """Return the first DEF- bone that is suitable as parent bone of given ORG- bone"""
    org_par = org_bone.parent
    if not org_par:
        return

    if org_par.name.startswith("MCH-"):  # MCH bones risk to be named after the bone we have started with
        return find_def_parent(ob, org_par)

    par_def_name = "DEF-{0}".format(org_par.name[4:])
    try:
        par_def = ob.pose.bones[par_def_name]
        return par_def
    except KeyError:
        return find_def_parent(ob, org_par)


def get_deform_root_name(ob):
    """Get the name first deform bone with no deform parent

    :param ob:
    :return:
    """
    # TODO
    return 'DEF-spine'


def get_deform_hips_name(ob, bone_name=None):
    """Starting from the root, get the first bone with more than one child

    :param ob: the armature object
    :param bone_name:
    :return: name of deform hips bone
    """
    if not bone_name:
        bone_name = get_deform_root_name(ob)

    bone = ob.data.edit_bones[bone_name]

    if len(bone.children) > 1:
        return bone_name

    return get_deform_hips_name(ob, bone.children[0].name)


def set_inherit_scale(ob, inherit_mode='FIX_SHEAR'):
    for bone in ob.data.edit_bones:
        if not bone.use_deform:
            continue

        bone.inherit_scale = inherit_mode


def copy_chain(ob, first, last_excluded=None, flip_bones=False):
    """Copy a chain of bones, return name of last copied bone"""
    bone = first

    prev_itd_bone = None
    while bone != last_excluded:
        bone_name = bone.name
        itd_name = bone_name.replace("DEF-", "ITD-")
        try:
            itd_bone = ob.data.edit_bones[itd_name]
        except KeyError:
            itd_name = copy_bone(ob, bone_name, assign_name=itd_name, constraints=True, deform_bone=False)
            itd_bone = ob.data.edit_bones[itd_name]

        itd_bone.use_deform = False
        itd_bone.parent = prev_itd_bone
        prev_itd_bone = itd_bone

        cp_name = copy_bone(ob, bone_name, assign_name=bone_name.replace("DEF-", "CP-"), constraints=False, deform_bone=False)
        cp_bone = ob.data.edit_bones[cp_name]
        cp_bone.use_deform = False

        cp_bone.parent = None

        if flip_bones:
            flip_bone(cp_bone)

        pbone = ob.pose.bones[bone_name]
        remove_bone_constraints(pbone)
        cp_loc = pbone.constraints.new('COPY_LOCATION')
        cp_rot = pbone.constraints.new('COPY_ROTATION')
        cp_scale = pbone.constraints.new('COPY_SCALE')
        for constr in (cp_loc, cp_rot, cp_scale):
            constr.target = ob
            constr.subtarget = cp_name

        cp_bone.parent = itd_bone

        # ITD- bones go to MCH layer
        for new_bone in (itd_bone, cp_bone):
            new_bone.layers[30] = True
            new_bone.layers[31] = False
            for i in range(30):
                new_bone.layers[i] = False

        if not bone.children:
            break
        bone = bone.children[0]
    
    return bone_name


def flip_bone(bone):
    bone.head, bone.tail = bone.tail.copy(), bone.head.copy()


def find_tail_root(ob, tail_start_name='DEF-tail.001'):
    try:
        tail_bone = get_edit_bone(ob, tail_start_name)
    except KeyError:
        return

    if not tail_bone:
        return

    while tail_bone.parent and is_def_bone(ob, tail_bone.parent.name):
        tail_bone = tail_bone.parent

    return tail_bone.name


def fix_tail_direction(ob):
    """Make the hips the actual root and parent the tail to it (Rigify tails are the other way around"""
    def_root_name = get_deform_root_name(ob)
    def_hips_name = get_deform_hips_name(ob, def_root_name)

    if def_root_name == def_hips_name:

        def_root_name = find_tail_root(ob)
        if not def_root_name:
            print("cannot figure root/hips, not fixing, tail")
            return def_hips_name

    def_root_edit = get_edit_bone(ob, def_root_name)
    def_hips_edit = get_edit_bone(ob, def_hips_name)

    tail_next_name = copy_chain(ob, def_root_edit, def_hips_edit, flip_bones=True)
    def_tail_next = get_edit_bone(ob, tail_next_name)
    def_tail_previous = def_hips_edit
    
    def_hips_edit.parent = None
    def_root_edit.parent = def_hips_edit

    while def_tail_next:
        if def_tail_next == def_hips_edit:
            break
        previous_parent = def_tail_next.parent
        
        def_tail_next.parent = None
        # flip bone
        flip_bone(def_tail_next)
        def_tail_next.parent = def_tail_previous
        if def_tail_previous is not def_hips_edit:
            def_tail_next.use_connect = True

        def_tail_previous = def_tail_next
        def_tail_next = previous_parent

    return def_hips_name


def copytransform_to_copylocrot(ob):
    for bone in ob.pose.bones:
        if not ob.data.bones[bone.name].use_deform:
            continue

        to_remove = []
        for constr in bone.constraints:
            if constr.type == 'COPY_TRANSFORM':
                to_remove.append(constr)
                for cp_constr in (pbone.constraints.new('COPY_ROTATION'), pbone.constraints.new('COPY_LOCATION')):
                    cp_constr.target = constr.ob
                    cp_constr.subtarget = constr.subtarget
            elif constr.type == 'STRETCH_TO':
                constr.mute = True

        for constr in to_remove:
            bone.constraints.remove(constr)


def limit_spine_scale(ob):
    for pbone in ob.pose.bones:
        if not ob.data.bones[pbone.name].use_deform:
            continue

        if not pbone.name.startswith('DEF-spine'):
            continue

        constr = pbone.constraints.new('LIMIT_SCALE')

        constr.min_x = 1
        constr.min_y = 1
        constr.min_z = 1

        constr.max_x = 1
        constr.max_y = 1
        constr.max_z = 1

        constr.use_min_x = True
        constr.use_min_y = True
        constr.use_min_z = True

        constr.use_max_x = True
        constr.use_max_y = True
        constr.use_max_z = True

        constr.owner_space = 'LOCAL'


def gamefriendly_hierarchy(ob, fix_tail=True, limit_scale=False):
    """Changes Rigify (0.5) rigs to a single root deformation hierarchy.
    Create ITD- (InTermeDiate) bones in the process"""
    assert(ob.mode == 'EDIT')

    pbones = list(ob.pose.bones)  # a list of pose bones is safer when switching through modes
    new_bone_names = []  # collect newly added bone names so that they can be edited later in Object Mode

    def_root_name = get_deform_root_name(ob)

    # we want deforming bone (i.e. the ones on layer 29) to have deforming bone parents
    for pbone in pbones:
        bone_name = pbone.name

        if not is_def_bone(ob, bone_name):
            continue
        if bone_name == def_root_name:
            continue
        if not pbone.parent:
            # root bones are fine
            continue
        if is_def_bone(ob, pbone.parent.name):
            continue
        if not bone_name.startswith("DEF-"):
            # we are only dealing with Rigify DEF- bones so far
            print("WARNING: {0}, not supported for Game Friendly Conversion".format(bone_name))
            continue

        # Intermediate Bone
        itd_name = bone_name.replace("DEF-", "ITD-")
        try:
            ob.data.edit_bones[itd_name]
        except KeyError:
            itd_name = copy_bone(ob, bone_name, assign_name=bone_name.replace("DEF-", "ITD-"), constraints=True, deform_bone=False)
            new_bone_names.append(itd_name)

        # DEF- bone will now follow the ITD- bone
        remove_bone_constraints(pbone)
        for cp_constr in (pbone.constraints.new('COPY_LOCATION'),
                          pbone.constraints.new('COPY_ROTATION'),
                          pbone.constraints.new('COPY_SCALE')):
            cp_constr.target = ob
            cp_constr.subtarget = itd_name

        # Look for a DEF- bone that would be a good parent. Unlike DEF- bones, ORG- bones retain the
        # hierarchy from the metarig, so we are going to reproduce the ORG- hierarchy
        org_name = "ORG-{0}".format(bone_name[4:])

        try:
            org_bone = ob.pose.bones[org_name]
        except KeyError:
            print("WARNING: 'ORG-' bone not found ({0})", org_name)
            continue
        else:
            def_par = find_def_parent(ob, org_bone)
            if not def_par:
                print("WARNING: Parent not found for {0}".format(bone_name))
                # as a last resort, look for a DEF- bone with the same name but a lower number
                # (i.e. try to parent DEF-tongue.002 to DEF-tongue.001)
                if bone_name[-4] == "." and bone_name[-3:].isdigit():
                    bname, number = bone_name.rsplit(".")
                    number = int(number)
                    if number > 1:
                        def_par_name = "{0}.{1:03d}".format(bname, number - 1)
                        print("Trying to use {0}".format(def_par_name))
                        try:
                            def_par = ob.pose.bones[def_par_name]
                        except KeyError:
                            print("No suitable DEF- parent for {0}".format(bone_name))
                            continue
                    else:
                        continue
                else:
                    continue

        ebone = get_edit_bone(ob, bone_name)
        ebone_par = get_edit_bone(ob, def_par.name)
        ebone.parent = ebone_par

    if fix_tail:
        new_root_name = fix_tail_direction(ob)
        if new_root_name:
            def_root_name = new_root_name

    if limit_scale:
        limit_spine_scale(ob)

    try:
        ob.data.edit_bones[def_root_name].parent = ob.data.edit_bones['root']
    except KeyError:
        print("WARNING: DEF hierarchy root was not parented to root bone")


class ConvertGameFriendly(bpy.types.Operator):
    """Convert Rigify (0.5) rigs to a Game Friendly hierarchy"""
    bl_idname = "armature.rigify_convert_gamefriendly"
    bl_label = "Rigify Game Friendly"
    bl_description = "Make the rigify deformation bones a one root rig"
    bl_options = {'REGISTER', 'UNDO'}

    keep_backup: BoolProperty(
        name="Backup",
        description="Keep copy of datablock",
        default=True
    )
    limit_scale: BoolProperty(
        name="Limit Spine Scale",
        description="Limit scale on the spine deform bones",
        default=True
    )
    fix_tail: BoolProperty(
        name="Invert Tail",
        description="Reverse the tail direction so that it spawns from hip",
        default=True
    )

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        if not obj:
            return False
        if obj.mode != 'EDIT':
            return False
        if obj.type != 'ARMATURE':
            return False
        return bool(context.active_object.data.get("rig_id"))

    def execute(self, context):
        ob = context.active_object
        if self.keep_backup:
            backup_data = ob.data.copy()
            backup_data.name = ob.name + "_GameUnfriendly_backup"
            backup_data.use_fake_user = True

        gamefriendly_hierarchy(ob, fix_tail=self.fix_tail, limit_scale=self.limit_scale)
        return {'FINISHED'}


class DATA_PT_rigify_makefriendly(bpy.types.Panel):
    bl_label = "Rigify Games"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "data"

    @classmethod
    def poll(cls, context):
        return context.object.type == 'ARMATURE' and bool(context.active_object.data.get("rig_id"))

    def draw(self, context):
        layout = self.layout
        obj = context.object

        if obj.mode == 'EDIT':
            pass

        # TODO: remove button, use right clic in edit mode
        row = layout.row()
        props = layout.operator("armature.rigify_convert_gamefriendly", text="Make Game Friendly")


def menu_func(self, context):
    self.layout.operator("armature.rigify_convert_gamefriendly")


def register():
    bpy.utils.register_class(ConvertGameFriendly)
    bpy.utils.register_class(DATA_PT_rigify_makefriendly)

    bpy.types.VIEW3D_MT_armature_context_menu.append(menu_func)


def unregister():
    bpy.utils.unregister_class(ConvertGameFriendly)
    bpy.utils.unregister_class(DATA_PT_rigify_makefriendly)

    bpy.types.VIEW3D_MT_armature_context_menu.append(menu_func)


if __name__ == "__main__":
    register()
