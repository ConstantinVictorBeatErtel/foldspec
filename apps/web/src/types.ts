import type {
  BuildResult as APIBuildResult,
  DesignProposal as APIDesignProposal,
  Finding as APIFinding,
  InspectionFeature as APIInspectionFeature,
  PartSpec as APIPartSpec,
  Project as APIProject,
  TemplateId as APITemplateId,
} from './generated/contracts'

export type TemplateId = APITemplateId
export type Feature = APIInspectionFeature
export type Finding = APIFinding
export type Spec = APIPartSpec
export type Build = APIBuildResult
export type Project = APIProject
export type Proposal = APIDesignProposal
