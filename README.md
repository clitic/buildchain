# musl-toolchains

## Install Dependencies

```bash
curl -L https://raw.githubusercontent.com/ninja-build/ninja/master/misc/ninja_syntax.py -o ninja_syntax.py
apt install bison flex gawk ninja-build patch texinfo
```

Also, see glibc [dependencies](https://github.com/bminor/glibc/blob/master/INSTALL).

## Build Toolchain

```bash
# download patches (optional)
python patches.py --musl-cross-make
```

```bash
python configure.py \
  --cc-flags "-static --static -g0 -Os" \
  --cxx-flags "-static --static -g0 -Os" \
  --ld-flags "-s " \
  --target x86_64-linux-musl
```

```bash
ninja install &> logs.txt
```

# L

https://github.com/ninja-build/ninja/blob/master/misc/ninja_syntax.py

https://github.com/ninja-build/ninja/blob/master/COPYING

#gnu vs llvm