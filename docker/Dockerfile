# Entorno del proyecto: gem5 v26.0.0.0 para ARM (MESI_Two_Level y MOESI_CMP_directory),
# libm5.a para AArch64 y compilador cruzado.
FROM ubuntu:24.04

ARG GEM5_VERSION=v26.0.0.0
ARG JOBS=4
ARG DEBIAN_FRONTEND=noninteractive

# 1. Dependencias de gem5 + compilador cruzado + Python para análisis
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential git m4 scons zlib1g-dev python3-dev pkg-config \
        libprotobuf-dev protobuf-compiler libprotoc-dev libgoogle-perftools-dev \
        libboost-all-dev libhdf5-dev libpng-dev ca-certificates \
        gcc-aarch64-linux-gnu g++-aarch64-linux-gnu \
        python3-pandas python3-matplotlib \
    && rm -rf /var/lib/apt/lists/*

# 2. Código fuente de gem5 (versión fija)
RUN git clone --branch ${GEM5_VERSION} --depth 1 https://github.com/gem5/gem5.git /opt/gem5
WORKDIR /opt/gem5

# 3. Una compilación por protocolo Ruby
COPY build_opts/ARM_MESI build_opts/ARM_MOESI /opt/gem5/build_opts/
RUN scons defconfig build/ARM_MESI build_opts/ARM_MESI \
 && scons build/ARM_MESI/gem5.opt -j${JOBS}
RUN scons defconfig build/ARM_MOESI build_opts/ARM_MOESI \
 && scons build/ARM_MOESI/gem5.opt -j${JOBS}

# 4. libm5.a para AArch64 (las m5ops que delimitan la ROI)
RUN cd util/m5 && scons build/arm64/out/m5

ENV GEM5_ROOT=/opt/gem5
WORKDIR /work
