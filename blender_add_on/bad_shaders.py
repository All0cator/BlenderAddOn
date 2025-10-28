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
    linearizedDepth = (depthLinear - near) / (far - near); // normalize depth
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
void main() {
    vec4 texel = texture(tex, fragTex);

    // single channel display as grayscale value
    vec4 singleChannel = vec4(texel.r, texel.r, texel.r, 1.0f);
    // multiple channels display as color value
    vec4 multipleChannels = texel;

    fragOut = singleChannel * (1.0f - isMultipleChannels) + multipleChannels * isMultipleChannels;
}
"""