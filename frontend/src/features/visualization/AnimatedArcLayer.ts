import { ArcLayer } from '@deck.gl/layers';
import type { ArcLayerProps } from '@deck.gl/layers';
import type { Accessor, DefaultProps } from '@deck.gl/core';

export type AnimatedArcLayerProps<DataT = any> = _AnimatedArcLayerProps<DataT> &
    ArcLayerProps<DataT>;

type _AnimatedArcLayerProps<DataT = any> = {
    getSourceTimestamp?: Accessor<DataT, number>;
    getTargetTimestamp?: Accessor<DataT, number>;
    timeRange?: [number, number];
};

const defaultProps: DefaultProps<_AnimatedArcLayerProps> = {
    getSourceTimestamp: { type: 'accessor', value: 0 },
    getTargetTimestamp: { type: 'accessor', value: 1 },
    timeRange: { type: 'array', compare: true, value: [0, 1] }
};

export default class AnimatedArcLayer<DataT = any, ExtraProps = {}> extends ArcLayer<
    DataT,
    ExtraProps & Required<_AnimatedArcLayerProps>
> {
    static layerName = 'AnimatedArcLayer';
    static defaultProps = defaultProps as any;

    // @ts-ignore
    getShaders() {
        const shaders = super.getShaders();
        shaders.inject = {
            'vs:#decl': `
in float instanceSourceTimestamp;
in float instanceTargetTimestamp;
out float vTimestamp;
`,
            'vs:#main-end': `
vTimestamp = mix(instanceSourceTimestamp, instanceTargetTimestamp, segmentRatio);
`,
            'fs:#decl': `
in float vTimestamp;
uniform vec2 timeRange;
`,
            'fs:#main-start': `
if (vTimestamp < timeRange.x || vTimestamp > timeRange.y) {
  discard;
}
`,
            'fs:DECKGL_FILTER_COLOR': `
color.a *= (vTimestamp - timeRange.x) / (timeRange.y - timeRange.x);
`
        };
        return shaders;
    }

    // @ts-ignore
    initializeState() {
        super.initializeState();
        this.getAttributeManager()?.addInstanced({
            instanceSourceTimestamp: {
                size: 1,
                accessor: 'getSourceTimestamp'
            },
            instanceTargetTimestamp: {
                size: 1,
                accessor: 'getTargetTimestamp'
            }
        });
    }

    // @ts-ignore
    draw(params: any) {
        const { timeRange } = this.props;
        const { model } = this.state;
        // @ts-ignore
        model.setUniforms({ timeRange });
        super.draw(params);
    }
}
