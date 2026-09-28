from __future__ import annotations

from typing import Any
import time

import wgpu
from rendercanvas.glfw import RenderCanvas, loop

from camera2d import *
from colormaterial import *
from transform import *
from disk import *
from quad import *
from texture import *
from sampler import *
from textureset import *
from node import *
from shader import *
from pipeline import *
from scene import *
from renderer import *
from engine import *

canvas: RenderCanvas
device: wgpu.GPUDevice
context: Any
renderer: Renderer
camera: Camera2D
scene: Scene
last_t: float = 0.0

class Orbit (Engine):
  # translação em círculo. refaz rotação+translação do zero a cada frame
  # (se acumular, o corpo só gira no lugar em vez de orbitar)
  def __init__ (self, trf: Transform, radius: float, speed: float, phase: float = 0.0) -> None:
    self.trf = trf
    self.radius = radius
    self.speed = speed
    self.angle = phase

  def update (self, dt: float) -> None:
    self.angle += self.speed * dt
    self.trf.load_identity()
    self.trf.rotate(self.angle, 0, 0, 1)
    self.trf.translate(self.radius, 0, 0)

class Spin (Engine):
  # rotação em torno do próprio eixo, sem translação
  def __init__ (self, trf: Transform, speed: float, phase: float = 0.0) -> None:
    self.trf = trf
    self.speed = speed
    self.angle = phase

  def update (self, dt: float) -> None:
    self.angle += self.speed * dt
    self.trf.load_identity()
    self.trf.rotate(self.angle, 0, 0, 1)

def initialize (device: wgpu.GPUDevice, target_format: str) -> None:
  global camera
  camera = Camera2D(-9, 9, -9, 9)

  shader = Shader(device, "../shaders/2d/textured.wgsl")
  shader.set_vertex_buffers([
    {"array_stride": 2 * 4, "step_mode": "vertex",
     "attributes": [{"format": "float32x2", "offset": 0, "var_name": "pos"}]},
    {"array_stride": 2 * 4, "step_mode": "vertex",
     "attributes": [{"format": "float32x2", "offset": 0, "var_name": "texcoord"}]},
  ])
  pipeline = Pipeline(shader, target_format, depth_stencil=None)

  # texturas (uma por imagem, reaproveitadas entre astros)
  space_tex = Texture(device, "decal_texture", "../images/space.png")
  space_smp = Sampler(device, "decal_sampler")
  space_ts = TextureSet([space_tex, space_smp])

  earth_tex = Texture(device, "decal_texture", "../images/earth.jpg")
  earth_smp = Sampler(device, "decal_sampler")
  earth_ts = TextureSet([earth_tex, earth_smp])

  # ruído genérico tingido de cor diferente em cada astro
  surface_tex = Texture(device, "decal_texture", "../images/noise.png")
  surface_smp = Sampler(device, "decal_sampler")
  surface_ts = TextureSet([surface_tex, surface_smp])

  shader.add_texture_set(space_ts)
  shader.add_texture_set(earth_ts)
  shader.add_texture_set(surface_ts)

  # fundo (quad cobrindo a tela toda)
  bg_trf = Transform()
  bg_trf.translate(-10, -10, 0)
  bg_trf.scale(20, 20, 1)
  bg_material = ColorMaterial(1, 1, 1)
  background = Node(trf=bg_trf, apps=[bg_material, space_ts], shps=[Quad(device)])

  # sol
  sun_trf = Transform()
  sun_trf.scale(1.5, 1.5, 1)
  sun_material = ColorMaterial(1.0, 0.8, 0.3)
  sun = Node(trf=sun_trf, apps=[sun_material, surface_ts], shps=[Disk(device)])

  # mercúrio
  mercury_orbit_trf = Transform()
  mercury_shape_trf = Transform()
  mercury_shape_trf.scale(0.35, 0.35, 1)
  mercury_material = ColorMaterial(0.65, 0.6, 0.55)
  mercury_shape = Node(trf=mercury_shape_trf, apps=[mercury_material, surface_ts], shps=[Disk(device)])
  mercury = Node(trf=mercury_orbit_trf, nodes=[mercury_shape])

  # terra: nó de spin separado do nó da lua, senão a lua herdaria a rotação
  earth_orbit_trf = Transform()
  earth_spin_trf = Transform()
  earth_shape_trf = Transform()
  earth_shape_trf.scale(0.7, 0.7, 1)
  earth_material = ColorMaterial(1, 1, 1)
  earth_shape = Node(trf=earth_shape_trf, apps=[earth_material, earth_ts], shps=[Disk(device)])
  earth_spin = Node(trf=earth_spin_trf, nodes=[earth_shape])

  moon_orbit_trf = Transform()
  moon_shape_trf = Transform()
  moon_shape_trf.scale(0.25, 0.25, 1)
  moon_material = ColorMaterial(0.75, 0.75, 0.78)
  moon_shape = Node(trf=moon_shape_trf, apps=[moon_material, surface_ts], shps=[Disk(device)])
  moon_orbit = Node(trf=moon_orbit_trf, nodes=[moon_shape])

  earth = Node(trf=earth_orbit_trf, nodes=[earth_spin, moon_orbit])

  shader.add_material(bg_material)
  shader.add_material(sun_material)
  shader.add_material(mercury_material)
  shader.add_material(earth_material)
  shader.add_material(moon_material)

  root = Node(pipeline, nodes=[background, sun, mercury, earth])
  global scene
  scene = Scene(root)
  scene.add_engine(Orbit(mercury_orbit_trf, radius=3.0, speed=55.0))
  scene.add_engine(Orbit(earth_orbit_trf, radius=6.0, speed=30.0))
  scene.add_engine(Spin(earth_spin_trf, speed=120.0))
  scene.add_engine(Orbit(moon_orbit_trf, radius=1.2, speed=160.0))

def update (dt: float) -> None:
  scene.update(dt)

def draw () -> None:
  global last_t
  t = time.perf_counter()
  update(t - last_t)
  last_t = t

  target_texture = context.get_current_texture()
  renderer.render(target_texture, scene, camera)

def on_key (event: Any) -> None:
  if event["key"] == "q":
    canvas.close()

def main () -> None:
  global canvas, device, context, renderer, last_t

  canvas = RenderCanvas(size=(700, 700), title="Projeto 1: mini sistema solar 2D", update_mode="continuous", max_fps=60)
  adapter = wgpu.gpu.request_adapter_sync()
  device = adapter.request_device_sync()
  context = canvas.get_context("wgpu")
  target_format = context.get_preferred_format(device.adapter)
  context.configure(device=device, format=target_format)

  renderer = Renderer(device, clear_value=(0.0, 0.0, 0.0, 1.0))

  initialize(device, target_format)

  canvas.add_event_handler(on_key, "key_down")
  last_t = time.perf_counter()
  canvas.request_draw(draw)
  loop.run()

if __name__ == "__main__":
  main()
