# Cats Blender Plugin for Blender 5.2

A fork of the [Unofficial Cats Blender Plugin](https://github.com/teamneoneko/Cats-Blender-Plugin) by Team Neoneko, which is no longer maintained. This fork targets **Blender 5.2 LTS only**.

Cats shortens the steps needed to import and optimize models for VRChat. It works with models from MMD, XNALara, Mixamo, Source Engine, Unreal Engine, DAZ/Poser, Blender Rigify, Sims 2, Motion Builder, 3DS Max and potentially more. Jobs that used to take hours of fixing are reduced to a few clicks.

> **Do not ask for help with this fork in the original Cats or Neoneko Discord servers.** They do not support it. Report problems with this fork on this repository instead.

## Blender version support

| Blender | Supported |
| --- | --- |
| 5.2.x LTS | Yes |
| 5.3 and newer | No, Cats refuses to load |
| 5.1 and older | No, use the [Neoneko releases](https://github.com/teamneoneko/Cats-Blender-Plugin/releases) for your version |

There is only one branch, and it is for Blender 5.2. The branches for older Blender versions were removed.

## Requirements

- Blender 5.2 from [blender.org](https://www.blender.org/download/) or Steam
- If Blender uses a custom Python installation, that installation needs NumPy

Not supported: the Windows Store version of Blender (known permission problems), and Linux package manager, Snap or Flatpak builds.

### Optional add-ons

- [Material Combiner](https://github.com/Grim-es/material-combiner-addon) for texture atlasing
- [Immersive Scaler](https://github.com/triazo/immersive_scaler) for the scaling tools

## Installation

1. Download `cats_blender_plugin-5.2.x.zip` from [Releases](https://github.com/DocMeVR/Cats-Blender-Plugin/releases), or [build it yourself](#building-from-source). Do not extract it.
2. In Blender 5.2, open **Edit > Preferences > Get Extensions**.
3. Open the drop-down menu in the top right corner and choose **Install from Disk...**. Dragging the zip into the Blender window works too.
4. Select the zip and make sure the extension is enabled.
5. Restart Blender.

If an older Cats version is installed, uninstall it first.

The Cats panel is in the 3D Viewport sidebar (press `N`) under the **CATS** tab.

## Updating

**Settings & Updates** in the Cats panel checks this repository's releases. Only releases whose tag starts with `5.2.` are offered.

## Building from source

Clone the repository and build the extension zip with Blender's own tool:

```bash
git clone https://github.com/DocMeVR/Cats-Blender-Plugin.git
blender --command extension build --source-dir Cats-Blender-Plugin --output-dir dist
```

The zip lands in `dist/`. Files listed under `[build]` in `blender_manifest.toml` (tests, CI files, local settings) are left out.

To create a release, set the same version in `CATS_VERSION` (`__init__.py`) and `version` (`blender_manifest.toml`), tag the commit with the full Cats version, for example `5.2.0.1`, and attach the zip to a GitHub release.

### Testing

`tests/smoke_test.py` loads Cats, draws every panel and runs the main tools on a generated test avatar, then exports and re-imports the result:

```bash
blender --background --factory-startup --python-exit-code 1 --python tests/smoke_test.py
```

Add `-- --model path/to/avatar.fbx` to test with your own model. Leave out `--background` to also test the tools that need a 3D Viewport. GitHub Actions runs the test against the built zip on every push to `main`.

## Features

- **Import/Export:** Optimized importing for MMD, VRM, FBX, Source Engine and more
- **Fix Model:** Renames, reparents and cleans the armature for VRChat in one click
- **Optimization:** Material combining, texture atlasing, bone merging
- **Eye Tracking:** SDK3 and legacy eye tracking setup
- **Visemes:** Automatic lip sync shape keys
- **Custom Model Creation:** Merge armatures and attach meshes
- **Translation:** Converts Japanese names to English
- **Manual tools:** Pose to shape key, apply pose as rest pose, separate and join meshes, merge weights and more

The [Neoneko Cats wiki](https://github.com/teamneoneko/Cats-Blender-Plugin/wiki) still describes the features of this fork:

- [Quick Access Guide](https://github.com/teamneoneko/Cats-Blender-Plugin/wiki/Quick-Access)
- [Optimization Tools](https://github.com/teamneoneko/Cats-Blender-Plugin/wiki/Optimization)
- [Eye Tracking Setup](https://github.com/teamneoneko/Cats-Blender-Plugin/wiki/Eye-Tracking)
- [Visemes Setup](https://github.com/teamneoneko/Cats-Blender-Plugin/wiki/Visemes)
- [Troubleshooting](https://github.com/teamneoneko/Cats-Blender-Plugin/wiki/Troubleshooting)
- [FAQ](https://github.com/teamneoneko/Cats-Blender-Plugin/wiki/FAQ)

## Changes from the Neoneko 5.0 version

- Runs on Blender 5.2 and its Python 3.13
- Includes the root bone fixes from the Neoneko `blender-5x-dev` branch
- Fixed a crash caused by applying settings from a background thread; settings now apply through a Blender timer
- The updater checks this repository's releases over verified HTTPS and no longer disables certificate checks for all of Blender
- Fixed errors when disabling the extension; its scene properties and shape key menu entry are now removed
- Fixed the eye tracking backup, which failed because `json` was not imported
- Fixed the Settings panel raising an error on every redraw
- Fixed a possible endless loop when removing doubles on meshes with shape keys
- Fixed hundreds of invalid escape sequence warnings in the bone name lists
- Removed code paths for Blender 2.7x to 4.x
- The extension manifest now passes `blender --command extension validate`
- **Download Latest Translations** now downloads from this repository. Before, it fetched the 5.0 texts from Neoneko and could overwrite the dictionary with a GitHub error page
- The Credits panel names this fork, and its **Support Us** button, which opened a page that no longer exists, is now **Report a Problem**

## Acknowledgements

Cats Blender Plugin was originally developed by [Absolute Quantum](https://github.com/absolute-quantum/cats-blender-plugin), then continued by Team Neoneko (Yusarina). This fork builds on their work.

Code contributors: Hotox, Shotariya, Neitri, Kiraver, Jordo, Ruubick, 989onan, rurre, Yusarina.

Cats uses these projects:

- [MMD Tools](https://github.com/MMD-Blender/blender_mmd_tools)
- [Immersive Scaler](https://github.com/triazo/immersive_scaler)
- [Material Combiner](https://github.com/Grim-es/material-combiner-addon)

## License

MIT, see [LICENSE](LICENSE).
