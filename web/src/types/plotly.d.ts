// The small part of Plotly the charts use (the package ships no types).
declare module "plotly.js-dist-min" {
  interface PlotlyElement extends HTMLDivElement {
    on(event: string, handler: (event: { points: PlotPoint[] }) => void): void;
    removeAllListeners?(event: string): void;
  }
  export interface PlotPoint {
    customdata: unknown;
    x: number | string;
    y: number | string;
    pointIndex: number;
    curveNumber: number;
  }
  const Plotly: {
    react(node: HTMLElement, data: object[], layout: object, config?: object): Promise<PlotlyElement>;
    purge(node: HTMLElement): void;
  };
  export default Plotly;
}
