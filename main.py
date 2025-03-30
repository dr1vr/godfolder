
from ursina import *
from ursina.prefabs.first_person_controller import FirstPersonController
import random
from perlin_noise import PerlinNoise
import json 
import os 
import math

# Initialize the Ursina engine
app = Ursina()

# Basic window setup
window.title = 'Voxel Game'
window.borderless = False; window.fullscreen = False; window.exit_button.visible = False
window.fps_counter.enabled = True; window.color = color.rgb(0, 180, 255)

# --- Scene Environment ---
scene.fog_density = 0.02 
scene.fog_color = window.color 
# --- Sky() and DirectionalLight() REMOVED again due to shader errors ---
# Sky()
# DirectionalLight(parent=scene, y=10, z=10, x=10, shadows=False) 
# scene.ambient_light = (.5, .5, .5, 1) 

# --- World Generation Parameters ---
CHUNK_SIZE = 8 
VIEW_DISTANCE = 3 
SEED = random.randint(1, 100000) 
noise = PerlinNoise(octaves=4, seed=SEED)
amp = 12 
freq = 48 
TREE_CHANCE = 0.02

# --- Load Assets (with fallback) ---
print("Loading assets...")
try:
    grass_texture  = load_texture('assets/grass.png'); dirt_texture   = load_texture('assets/dirt.png'); 
    stone_texture  = load_texture('assets/stone.png'); wood_texture   = load_texture('assets/wood.png'); 
    leaves_texture = load_texture('assets/leaves.png')
    block_model    = 'assets/block'
    print("Custom assets loaded.")
except Exception as e:
    print(f"Error loading custom assets: {e}. Falling back to defaults.")
    grass_texture = 'white_cube'; dirt_texture = 'white_cube'; stone_texture = 'white_cube'
    wood_texture = 'white_cube'; leaves_texture = 'white_cube'; block_model = 'cube'

# --- Block Definitions ---
block_colors = { # Used if textures fail
    'grass': color.hsv(120, 0.8, 0.8), 'dirt':  color.hsv(30, 0.7, 0.6),
    'stone': color.hsv(0, 0, 0.5), 'wood':  color.hsv(30, 0.9, 0.4),
    'leaves':color.hsv(100, 0.8, 0.7)
}
block_textures = { # Maps type name to texture
    'grass': grass_texture, 'dirt': dirt_texture, 'stone': stone_texture,
    'wood': wood_texture, 'leaves': leaves_texture
}
block_types = list(block_colors.keys()) 
current_block_index = 0 
current_block_type = block_types[current_block_index]

# --- Chunk Management (unchanged) ---
loaded_chunks = {} 
player_chunk_pos = (0, 0)

# --- UI Elements (unchanged) ---
ui_parent = Panel(origin=(-.5, -.5), scale=0.1, position=window.bottom_left + Vec2(0.05, 0.05))
ui_panels = {}
for i, b_type in enumerate(block_types):
    panel_color = color.white if block_textures[b_type] != 'white_cube' else block_colors[b_type]
    panel = Panel(parent=ui_parent, model='quad', texture=block_textures[b_type],
                  color=panel_color, origin=(-0.5, -0.5), 
                  position=(i * 1.1, 0), scale=0.8)
    ui_panels[b_type] = panel
ui_panels[current_block_type].scale = 1.0 
ui_panels[current_block_type].z = -1 
crosshair = Text(text='+', origin=(0,0), scale=1, color=color.white, background=False)

# --- Voxel Class (Only for PLACED blocks - unchanged) ---
class Voxel(Button):
    def __init__(self, position=(0,0,0), block_type='grass'): 
        self.block_type = block_type
        use_texture = block_textures.get(block_type, 'white_cube')
        use_color = color.white if use_texture != 'white_cube' else block_colors.get(block_type, color.magenta)
        super().__init__(parent = scene, position=position, model=block_model, 
                       origin_y=0.5, texture=use_texture, color=use_color,
                       highlight_color=color.lime, collider='box')

# --- Save/Load Function (DISABLED - unchanged) ---
def save_world(): print("Save/Load is disabled.")
def load_world(): print("Save/Load is disabled.")

# --- Manual Mesh Generation Data (unchanged) ---
cube_verts_24 = (
    Vec3(-0.5,-0.5,-0.5), Vec3( 0.5,-0.5,-0.5), Vec3( 0.5, 0.5,-0.5), Vec3(-0.5, 0.5,-0.5),
    Vec3(-0.5,-0.5, 0.5), Vec3( 0.5,-0.5, 0.5), Vec3( 0.5, 0.5, 0.5), Vec3(-0.5, 0.5, 0.5),
    Vec3(-0.5, 0.5,-0.5), Vec3( 0.5, 0.5,-0.5), Vec3( 0.5, 0.5, 0.5), Vec3(-0.5, 0.5, 0.5),
    Vec3(-0.5,-0.5,-0.5), Vec3( 0.5,-0.5,-0.5), Vec3( 0.5,-0.5, 0.5), Vec3(-0.5,-0.5, 0.5),
    Vec3(-0.5,-0.5,-0.5), Vec3(-0.5,-0.5, 0.5), Vec3(-0.5, 0.5, 0.5), Vec3(-0.5, 0.5,-0.5),
    Vec3( 0.5,-0.5,-0.5), Vec3( 0.5,-0.5, 0.5), Vec3( 0.5, 0.5, 0.5), Vec3( 0.5, 0.5,-0.5),
)
cube_tris_24 = []; 
for i in range(6): offset = i*4; cube_tris_24.extend([offset+0, offset+1, offset+2, offset+0, offset+2, offset+3])
cube_uvs_24 = (Vec2(0,0), Vec2(1,0), Vec2(1,1), Vec2(0,1)) * 6

# --- Generate Chunk Function (Optimized Meshing + Trees - unchanged) ---
def generate_chunk(cx, cz):
    chunk_key = (cx, cz)
    if chunk_key in loaded_chunks: return
    chunk_entity = Entity(parent=scene) 
    loaded_chunks[chunk_key] = chunk_entity
    block_data = {'grass': [], 'dirt': [], 'stone': [], 'wood': [], 'leaves': []}
    base_x = cx * CHUNK_SIZE; base_z = cz * CHUNK_SIZE
    for z_offset in range(CHUNK_SIZE):
        for x_offset in range(CHUNK_SIZE):
            world_x = base_x + x_offset; world_z = base_z + z_offset
            y = math.floor(noise([world_x / freq, world_z / freq]) * amp)
            grass_pos = Vec3(world_x, y, world_z)
            block_data['grass'].append(grass_pos)
            for dy in range(y - 1, y - 4, -1): block_data['dirt'].append(Vec3(world_x, dy, world_z))
            for dy in range(y - 4, y - 7, -1): block_data['stone'].append(Vec3(world_x, dy, world_z))
            if random.random() < TREE_CHANCE:
                for i in range(1, 5): block_data['wood'].append(grass_pos + Vec3(0, i, 0))
                leaves_base_y = y + 4
                for lx in range(-1, 2):
                    for ly in range(0, 2):
                        for lz in range(-1, 2):
                            if lx == 0 and lz == 0 and ly == 0: continue
                            if random.random() < 0.8: 
                                block_data['leaves'].append(grass_pos + Vec3(lx, leaves_base_y + ly, lz))
    for b_type, pos_list in block_data.items():
        if pos_list:
            chunk_verts = []; chunk_tris = []; chunk_uvs = []; chunk_colors = []
            vertex_count = 0
            use_texture = block_textures.get(b_type, 'white_cube')
            use_color = color.white if use_texture != 'white_cube' else block_colors.get(b_type, color.magenta)
            for pos in pos_list:
                for vert in cube_verts_24: chunk_verts.append(vert + pos)
                chunk_uvs.extend(cube_uvs_24)
                vertex_color = block_colors.get(b_type, color.magenta)
                chunk_colors.extend([vertex_color] * 24)
                for tri_index in cube_tris_24: chunk_tris.append(tri_index + vertex_count)
                vertex_count += 24
            Entity(
                parent=chunk_entity, 
                model=Mesh(vertices=chunk_verts, triangles=chunk_tris, uvs=chunk_uvs, colors=chunk_colors, static=True), 
                texture=use_texture, color=use_color, collider='mesh'
            )

# --- Update UI Highlight Function (unchanged) ---
def update_ui_highlight():
    for b_type, panel in ui_panels.items():
        panel.scale = 1.0 if b_type == current_block_type else 0.8
        panel.z = -1 if b_type == current_block_type else 0

# --- Global input handling (unchanged) ---
def input(key):
    global current_block_type, current_block_index
    block_changed = False
    if key.isdigit() and 1 <= int(key) <= len(block_types):
        new_index = int(key) - 1
        if new_index != current_block_index: current_block_index = new_index; block_changed = True
    elif key == 'scroll up': current_block_index = (current_block_index + 1) % len(block_types); block_changed = True
    elif key == 'scroll down': current_block_index = (current_block_index - 1) % len(block_types); block_changed = True
    if block_changed: 
        current_block_type = block_types[current_block_index]
        print(f"Selected {current_block_type.capitalize()}"); update_ui_highlight()
    if key == 'left mouse down':
        if mouse.hovered_entity and isinstance(mouse.hovered_entity, Voxel):
            destroy(mouse.hovered_entity)
    if key == 'right mouse down':
        if mouse.hovered_entity and mouse.normal:
             Voxel(position=mouse.world_point + mouse.normal, block_type=current_block_type)
    if key == 'f5': save_world()
    if key == 'f6': load_world()

# --- Update Function (unchanged) ---
def update():
    global player_chunk_pos
    current_cx = math.floor(player.x / CHUNK_SIZE); current_cz = math.floor(player.z / CHUNK_SIZE)
    current_player_chunk_pos = (current_cx, current_cz)
    if current_player_chunk_pos != player_chunk_pos:
        player_chunk_pos = current_player_chunk_pos
        required_chunks = set()
        for cz in range(current_cz - VIEW_DISTANCE, current_cz + VIEW_DISTANCE + 1):
            for cx in range(current_cx - VIEW_DISTANCE, current_cx + VIEW_DISTANCE + 1):
                required_chunks.add((cx, cz))
        chunks_to_unload = set(loaded_chunks.keys()) - required_chunks
        for chunk_key in chunks_to_unload:
            if chunk_key in loaded_chunks: destroy(loaded_chunks[chunk_key]); del loaded_chunks[chunk_key]
        chunks_to_load = required_chunks - set(loaded_chunks.keys())
        for chunk_key in chunks_to_load: generate_chunk(chunk_key[0], chunk_key[1])

# --- Initial World Generation (unchanged) ---
print("Generating initial chunks with trees...")
player_start_x = 0; player_start_z = 0
start_cx = math.floor(player_start_x / CHUNK_SIZE); start_cz = math.floor(player_start_z / CHUNK_SIZE)
player_chunk_pos = (start_cx, start_cz)
for cz in range(start_cz - VIEW_DISTANCE, start_cz + VIEW_DISTANCE + 1):
    for cx in range(start_cx - VIEW_DISTANCE, start_cx + VIEW_DISTANCE + 1):
        generate_chunk(cx, cz)
print("Initial generation complete.")

# --- Add the First Person Controller (unchanged) ---
player_start_y = 30 
player = FirstPersonController(x=player_start_x, y=player_start_y, z=player_start_z, origin_y=-0.5) 
player.cursor.visible = False 

# --- Run the game ---
app.run()
