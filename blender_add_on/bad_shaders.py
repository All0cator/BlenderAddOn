#  ***** GPL LICENSE BLOCK *****
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.
#  All rights reserved.
#  ***** GPL LICENSE BLOCK *****

vertex_shader_source_object_id_depth = """
//layout(location = 0) in vec3 pos;

// uniform mat4 mvp;

void main() {
    gl_Position = mvp * vec4(pos, 1.0f);
}
"""

fragment_shader_source_object_id_depth = """
//layout(location = 0) out float objectID;
//layout(location = 1) out float linearizedDepth;

//uniform float near; // Near and far plane values in projection matrix
//uniform float far;
//uniform float id;

float LinearizeDepth(float d) {
    // Normalize Depth to NDC space[-1, 1] from clip space [0, 1]
    float Dndc = 2.0f * d - 1.0f;
    // Linearize Depth to [near, far] from [-1, 1]
    return (2.0f * near * far) / (far + near - Dndc * (far - near));
}

void main() {
    float depthLinear = LinearizeDepth(gl_FragCoord.z);
    objectID = id;
    linearizedDepth = depthLinear;
}
"""



vertex_shader_source_texture_display = """
// layout(location = 0) in vec2 pos;
// layout(location = 1) in vec2 texCoord;

// out vec2 fragTex;

void main() {
    fragTex = texCoord;
    gl_Position = vec4(pos, 0.0f, 1.0f);
}
"""

fragment_shader_source_texture_display = """
//in vec2 fragTex;

//layout(location = 0) out vec4 fragOut; 

//uniform sampler2D tex;
//uniform float isMultipleChannels; // 1.0f or 0.0f
// if normalization is not desired because it already displays color data specify max = 1.0 and min = 0.0
//uniform float channelMin;
//uniform float channelMax; 

float NormalizeChannel(float c) {
    return (c - channelMin) / (channelMax - channelMin);
}

void main() {
    vec4 texel = texture(tex, vec2(fragTex.x, fragTex.y));
    
    float rNormalized = NormalizeChannel(texel.r);
    float gNormalized = NormalizeChannel(texel.g);
    float bNormalized = NormalizeChannel(texel.b);
    float aNormalized = NormalizeChannel(texel.a);

    // single channel display as grayscale value
    vec4 singleChannel = vec4(rNormalized, rNormalized, rNormalized, 1.0f);
    // multiple channels display as color value
    vec4 multipleChannels = vec4(rNormalized, gNormalized, bNormalized, aNormalized);

    fragOut = singleChannel * (1.0f - isMultipleChannels) + multipleChannels * isMultipleChannels;
}
"""

compute_shader_source_sprite_atlas_render_channels = """
//#version 430 core

// #define MAX_CELL_VIEWPORTS 100
//layout(local_size_x = 8, local_size_y = 8, local_size_z = 1) in;
//uniform float viewportWidth;
//uniform float viewportHeight;

// SSBOs not supported 
//layout(std430, binding = 0) buffer objectIDToCellViewport {
//    vec4 cellViewports[];
//    // (x, y, width, height)
//};

//layout(binding = 0, std140) uniform cellViewports {
//    vec4[MAX_CELL_VIEWPORTS] _cellViewports;
//};

// Images
//layout(binding = 1, r32f) uniform readonly image2D objectIDs;
//layout(binding = 2, rgba8) uniform readonly image2D colors;
//layout(binding = 3, r32ui) uniform uimage2D spriteAtlasR;
//layout(binding = 4, r32ui) uniform uimage2D spriteAtlasG;
//layout(binding = 5, r32ui) uniform uimage2D spriteAtlasB;
//layout(binding = 6, r32ui) uniform uimage2D spriteAtlasAverageDenominator;

void main() {
    if(gl_GlobalInvocationID.x * 4 >= viewportWidth || gl_GlobalInvocationID.y * 4 >= viewportHeight) {
        return;
    }

    for(int y = 0; y < 4; ++y) {
        if (gl_GlobalInvocationID.y * 4 + y >= viewportHeight) return;
        for(int x = 0; x < 4; ++x) {
            if(gl_GlobalInvocationID.x * 4 + y >= viewportWidth) break;
            int yy = int(gl_GlobalInvocationID.y) * 4 + y;
            int xx = int(gl_GlobalInvocationID.x) * 4 + x;
            float id = imageLoad(objectIDs, ivec2(xx, yy)).r;
            vec4 cellViewport = _cellViewports[min(int(id), MAX_CELL_VIEWPORTS - 1)];
            
            // for now calculate each time pixel_size to be used as the denominator when calculating average
            float cellPixelSize = (viewportWidth / cellViewport.z) *  (viewportHeight / cellViewport.w);

            // map (xx, yy) to (xxAtlas, yyAtlas)

			// (0, 0) -> (cellViewport.x, cellViewport.y)
			// (viewportWidth, viewportHeight) -> (cellViewport.x + cellViewport.z, cellViewport.y + cellViewport.w)

			// (xx, yy) -> ((xx / viewportWidth) * cellViewport.z + cellViewport.x, (yy / viewport_height) * cellViewport.w + cellViewport.y)

			int xxAtlas = int(floor((float(xx) / viewportWidth) * cellViewport.z + cellViewport.x));
			int yyAtlas = int(floor((float(yy) / viewportHeight) * cellViewport.w + cellViewport.y));

            vec4 color = vec4(0.0, 0.0, 0.0, 1.0) * max(1.0f - id, 0.0f) + min(id, 1.0f) * imageLoad(colors, ivec2(xx, yy));

            imageAtomicAdd(spriteAtlasR, ivec2(xxAtlas, yyAtlas), uint(color.r * 255.0f));
            imageAtomicAdd(spriteAtlasG, ivec2(xxAtlas, yyAtlas), uint(color.g * 255.0f));
            imageAtomicAdd(spriteAtlasB, ivec2(xxAtlas, yyAtlas), uint(color.b * 255.0f));
            imageAtomicAdd(spriteAtlasAverageDenominator, ivec2(xxAtlas, yyAtlas), 1);
        }
    }
}
"""

compute_shader_source_sprite_atlas_merge_channels_to_texture = """
//#version 430 core

//layout(local_size_x = 32, local_size_y = 1, local_size_z = 1) in;
//uniform float atlasWidth;
//uniform float atlasHeight;

// Images
//layout(binding = 3, r32ui) uniform readwrite uimage2D spriteAtlasR;
//layout(binding = 4, r32ui) uniform readwrite uimage2D spriteAtlasG;
//layout(binding = 5, r32ui) uniform readwrite uimage2D spriteAtlasB;
//layout(binding = 6, rgba8) uniform writeonly image2D spriteAtlas;
//layout(binding = 7, r32ui) uniform readonly uimage2D spriteAtlasAverageDenominator;

void main() {
    if(gl_GlobalInvocationID.x >= atlasWidth * atlasHeight) {
        return;
    }

    // copy atlas channels to atlas texture
    ivec2 coords = ivec2(int(mod(float(gl_GlobalInvocationID.x), atlasWidth)), ceil(float(gl_GlobalInvocationID.x) / atlasWidth));
    float d = imageLoad(spriteAtlasAverageDenominator, coords).r;
    float r = imageLoad(spriteAtlasR, coords).r / (d * 255.0f);
    float g = imageLoad(spriteAtlasR, coords).r / (d * 255.0f);
    float b = imageLoad(spriteAtlasR, coords).r / (d * 255.0f);

    vec4 color = vec4(r, g, b, 1.0f);
    imageStore(spriteAtlas, coords, color);
    // clear sprite atlases
    imageStore(spriteAtlasAverageDenominator, coords, uvec4(0));
    imageStore(spriteAtlasR, coords, uvec4(0));
    imageStore(spriteAtlasB, coords, uvec4(0));
    imageStore(spriteAtlasG, coords, uvec4(0));
}
"""

compute_shader_source_combined_render = """
// #define MAX_CELL_VIEWPORTS 100

// layout(local_size_x = 32, local_size_y = 1, local_size_z = 1) in;
//uniform float viewportWidth;
//uniform float viewportHeight;

//layout(binding = 0, std140) uniform cellViewports {
//    vec4[MAX_CELL_VIEWPORTS] _cellViewports;
//};

//layout(binding = 1, r32f) uniform readonly image2D objectIDs;
//layout(binding = 2, rgba8) uniform readonly image2D colors;
//layout(binding = 6, rgba8) uniform readonly image2D spriteAtlas;
//layout(binding = 7, rgba8) uniform writeonly image2D combinedRender;

void main() {
    if(gl_GlobalInvocationID.x >= viewportWidth * viewportHeight) {
        return;
    }

    // combine spriteAtlas with colors using objectIDs
    ivec2 coords = ivec2(int(mod(float(gl_GlobalInvocationID.x), viewportWidth)), ceil((float(gl_GlobalInvocationID.x) / viewportWidth)));
    float id = imageLoad(objectIDs, coords).r;
    vec4 cellViewport = _cellViewports[min(int(id), MAX_CELL_VIEWPORTS - 1)];
    vec4 color = vec4(0.0, 0.0, 0.0, 1.0);

    ivec2 sampleCoords = ivec2(
    int(floor((float(coords.x) / viewportWidth) * cellViewport.z + cellViewport.x)),
    int(floor((float(coords.y) / viewportHeight) * cellViewport.w + cellViewport.y))
    );

    if(id == 0.0f) {
        color = imageLoad(colors, coords);
    } else {
        // get it from the spriteAtlas
        color = imageLoad(spriteAtlas, sampleCoords);
    }
    
    // write color to combinedRender
    imageStore(combinedRender, coords, color);
}
"""
