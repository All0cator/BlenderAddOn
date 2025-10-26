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
//in vec3 pos;

// uniform mat4 mvp;

void main() {
    gl_Position = mvp * vec4(pos, 1.0);
}
"""

fragment_shader_source_object_id_depth = """
//out float objectID;
//out float linearizedDepth;

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