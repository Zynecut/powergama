# -*- coding: utf-8 -*-
"""
Created on Tue Aug 16 13:21:21 2016

@author: Martin Kristiansen, Harald Svendsen
"""


import pyomo.environ as pyo
import pandas as pd
import numpy as np
import sklearn.cluster
import sklearn.preprocessing
import pyomo.pysp.scenariotree.tree_structure_model as tsm
import networkx


class SipModel():
    '''
    Power Grid Investment Module - stochastic investment problem
    '''
    
    _NUMERICAL_THRESHOLD_ZERO = 1e-6
    _HOURS_PER_YEAR = 8760
    
    def __init__(self, M_const = 1000):
        """Create Abstract Pyomo model for PowerGIM
        
        Parameters
        ----------
        M_const : int
            large constant
        """
        self.abstractmodel = self._createAbstractModel()
        self.M_const = M_const

        
        
    
    def _createAbstractModel(self):    
        model = pyo.AbstractModel()
        model.name = 'PowerGIM abstract model'
        
        # SETS ###############################################################
        
        model.NODE = pyo.Set()
        model.GEN = pyo.Set()
        model.BRANCH = pyo.Set()
        model.LOAD = pyo.Set()
        model.AREA = pyo.Set()
        model.TIME = pyo.Set()
        model.STAGE = pyo.Set()
        
        #A set for each stage i.e. a list with two sets
        model.NODE_EXPAND1 = pyo.Set()
        model.NODE_EXPAND2 = pyo.Set()
        model.BRANCH_EXPAND1 = pyo.Set()
        model.BRANCH_EXPAND2 = pyo.Set()
        model.GEN_EXPAND1 = pyo.Set()
        model.GEN_EXPAND2 = pyo.Set()
        
        model.BRANCHTYPE = pyo.Set()
        model.BRANCHCOSTITEM = pyo.Set(initialize=['B','Bd', 'Bdp', 
                                                   'CLp','CL','CSp','CS'])        
        model.NODETYPE = pyo.Set()
        model.NODECOSTITEM = pyo.Set(initialize=['L','S'])
        model.LINEAR = pyo.Set(initialize=['fix','slope'])
        
        model.GENTYPE = pyo.Set()
        

        # PARAMETERS #########################################################
        model.samplefactor = pyo.Param(model.TIME, within=pyo.NonNegativeReals)
        model.financeInterestrate = pyo.Param(within=pyo.Reals)
        model.financeYears = pyo.Param(within=pyo.Reals)
        model.omRate = pyo.Param(within=pyo.Reals)
        model.CO2price = pyo.Param(within=pyo.NonNegativeReals)
        model.VOLL = pyo.Param(within=pyo.NonNegativeReals)
        model.stage2TimeDelta = pyo.Param(within=pyo.NonNegativeReals)
        model.maxNewBranchNum = pyo.Param(within=pyo.NonNegativeReals)
        
        #investment costs and limits:        
        model.branchtypeMaxCapacity = pyo.Param(model.BRANCHTYPE,
                                                within=pyo.Reals)
        model.branchMaxNewCapacity = pyo.Param(model.BRANCH,within=pyo.Reals)
        model.branchtypeCost = pyo.Param(model.BRANCHTYPE, 
                                         model.BRANCHCOSTITEM,
                                         within=pyo.Reals)
        model.branchLossfactor = pyo.Param(model.BRANCHTYPE,model.LINEAR,
                                     within=pyo.Reals)
        model.nodetypeCost = pyo.Param(model.NODETYPE, model.NODECOSTITEM,
                                       within=pyo.Reals)
        model.genTypeCost = pyo.Param(model.GENTYPE, within=pyo.Reals)
        model.nodeCostScale = pyo.Param(model.NODE,within=pyo.Reals)
        model.branchCostScale = pyo.Param(model.BRANCH,within=pyo.Reals)
        model.genCostScale = pyo.Param(model.GEN, within=pyo.Reals)
        model.genNewCapMax = pyo.Param(model.GEN, within=pyo.Reals)
        
        #branches:
        model.branchExistingCapacity = pyo.Param(model.BRANCH, 
                                                 within=pyo.NonNegativeReals)
        model.branchExistingCapacity2 = pyo.Param(model.BRANCH, 
                                                 within=pyo.NonNegativeReals)
        model.branchExpand = pyo.Param(model.BRANCH,
                                       within=pyo.Binary)  
        model.branchExpand2 = pyo.Param(model.BRANCH,
                                       within=pyo.Binary)
        model.branchDistance = pyo.Param(model.BRANCH, 
                                         within=pyo.NonNegativeReals)                                             
        model.branchType = pyo.Param(model.BRANCH,within=model.BRANCHTYPE)
        model.branchOffshoreFrom = pyo.Param(model.BRANCH,within=pyo.Binary)
        model.branchOffshoreTo = pyo.Param(model.BRANCH,within=pyo.Binary)
    
        #nodes:
        model.nodeExistingNumber = pyo.Param(model.NODE, 
                                             within=pyo.NonNegativeIntegers)
        model.nodeOffshore = pyo.Param(model.NODE, within=pyo.Binary)
        model.nodeType = pyo.Param(model.NODE, within=model.NODETYPE)
        
        #generators
        model.genCostAvg = pyo.Param(model.GEN, within=pyo.Reals)
        model.genCostProfile = pyo.Param(model.GEN,model.TIME,
                                         within=pyo.Reals)
        model.genCapacity = pyo.Param(model.GEN,within=pyo.Reals)
        model.genCapacity2 = pyo.Param(model.GEN,within=pyo.Reals)
        model.genCapacityProfile = pyo.Param(model.GEN,model.TIME,
                                          within=pyo.Reals)
        model.genPAvg = pyo.Param(model.GEN,within=pyo.Reals)
        model.genType = pyo.Param(model.GEN, within=model.GENTYPE)
        model.genExpand = pyo.Param(model.GEN, 
                                    within=pyo.Binary)
        model.genExpand2 = pyo.Param(model.GEN, 
                                    within=pyo.Binary)
        model.genTypeEmissionRate = pyo.Param(model.GENTYPE, within=pyo.Reals)
        
        #helpers:
        model.genNode = pyo.Param(model.GEN,within=model.NODE)
        model.demNode = pyo.Param(model.LOAD,within=model.NODE)
        model.branchNodeFrom = pyo.Param(model.BRANCH,within=model.NODE)
        model.branchNodeTo = pyo.Param(model.BRANCH,within=model.NODE)
        model.nodeArea = pyo.Param(model.NODE,within=model.AREA)
        
        #consumers
        # the split int an average value, and a profile is to make it easier
        # to generate scenarios (can keep profile, but adjust demandAvg)
        model.demandAvg = pyo.Param(model.LOAD,within=pyo.Reals)
        model.demandProfile = pyo.Param(model.LOAD,model.TIME,
                                        within=pyo.Reals)
        model.emissionCap = pyo.Param(model.LOAD, within=pyo.NonNegativeReals)
        
        # VARIABLES ##########################################################
    
        # investment: new branch capacity
        def branchNewCapacity_bounds(model,j,h):
            if h>1:
                return (0,model.branchMaxNewCapacity[j]*model.branchExpand2[j])
            else:
                return (0,model.branchMaxNewCapacity[j]*model.branchExpand[j])
        model.branchNewCapacity = pyo.Var(model.BRANCH, model.STAGE, 
                                          within = pyo.NonNegativeReals,
                                          bounds = branchNewCapacity_bounds)                                  

        # investment: new branch cables
        def branchNewCables_bounds(model,j,h):
            if h>1:
                return (0,model.maxNewBranchNum*model.branchExpand2[j])
            else:
                return (0,model.maxNewBranchNum*model.branchExpand[j])                                  
        model.branchNewCables = pyo.Var(model.BRANCH, model.STAGE, 
                                        within = pyo.NonNegativeIntegers,
                                        bounds = branchNewCables_bounds)
                                        

        # investment: new nodes
        model.newNodes = pyo.Var(model.NODE, model.STAGE, within = pyo.Binary)

        
        # investment: generation capacity
        def genNewCapacity_bounds(model,g,h):
            if h>1:
                return (0,model.genNewCapMax[g]*model.genExpand2[g])
            else:
                return (0,model.genNewCapMax[g]*model.genExpand[g])
        model.genNewCapacity = pyo.Var(model.GEN, model.STAGE,
                                       within = pyo.NonNegativeReals,
                                       bounds = genNewCapacity_bounds)

        
        # branch power flow (also given by constraints??)
        def branchFlow_bounds(model,j,t,h):
            if h == 1:
                ub = (model.branchExistingCapacity[j]+
                        branchNewCapacity_bounds(model,j,h)[1])
            elif h == 2:
                ub = (model.branchExistingCapacity[j]+
                        model.branchExistingCapacity2[j]+
                        branchNewCapacity_bounds(model,j,h-1)[1]+
                        branchNewCapacity_bounds(model,j,h)[1])
            return (0,ub)
        model.branchFlow12 = pyo.Var(model.BRANCH, model.TIME,model.STAGE, 
                                     within = pyo.NonNegativeReals,
                                     bounds = branchFlow_bounds)
        model.branchFlow21 = pyo.Var(model.BRANCH, model.TIME, model.STAGE,
                                     within = pyo.NonNegativeReals,
                                     bounds = branchFlow_bounds)

        
        # generator output (bounds set by constraint)
        model.generation = pyo.Var(model.GEN, model.TIME,model.STAGE, 
                                   within = pyo.NonNegativeReals)
        # load shedding
        def loadShed_bounds(model, n, t, h):
            ub = 0
            for c in model.LOAD:
                if model.demNode[c]==n:
                    ub += model.demandAvg[c]*model.demandProfile[c,t]
            return (0,ub)
        model.loadShed = pyo.Var(model.NODE, model.TIME, model.STAGE,
                                 domain = pyo.NonNegativeReals,
                                 bounds = loadShed_bounds) 
        
        
        
        # CONSTRAINTS ########################################################

        # Power flow limitations (in both directions)                
        def maxflow12_rule(model,j,t,h):
            cap = model.branchExistingCapacity[j]
            if h >1:
                cap += model.branchExistingCapacity2[j]
            for x in range(h):
                cap += model.branchNewCapacity[j,x+1]
            expr = (model.branchFlow12[j,t,h] <= cap)
            return expr
            
        def maxflow21_rule(model,j,t,h):
            cap = model.branchExistingCapacity[j]
            if h >1:
                cap += model.branchExistingCapacity2[j]
            for x in range(h):
                cap += model.branchNewCapacity[j,x+1]
            expr = (model.branchFlow21[j,t,h] <= cap)
            return expr
        
        model.cMaxFlow12 = pyo.Constraint(model.BRANCH, model.TIME,model.STAGE, 
                                         rule=maxflow12_rule)
        model.cMaxFlow21 = pyo.Constraint(model.BRANCH, model.TIME,model.STAGE,
                                         rule=maxflow21_rule)
                                         
        # No new branch capacity without new cables
        def maxNewCap_rule(model,j,h):
            typ = model.branchType[j]
            expr = (model.branchNewCapacity[j,h] 
                    <= model.branchtypeMaxCapacity[typ]
                        *model.branchNewCables[j,h])
            return expr
        model.cmaxNewCapacity = pyo.Constraint(model.BRANCH, model.STAGE,
                                               rule=maxNewCap_rule)

                                            
        # A node required at each branch endpoint
        def newNodes_rule(model,n,h):
            expr = 0
            numnodes = model.nodeExistingNumber[n]
            for x in range(h):
                numnodes += model.newNodes[n,x+1]
            for j in model.BRANCH:
                if model.branchNodeFrom[j]==n or model.branchNodeTo[j]==n:
                    expr += model.branchNewCables[j,h]
            expr = (expr <= self.M_const * numnodes)
            if ((type(expr) is bool) and (expr==True)):
                expr = pyo.Constraint.Skip
            return expr
        model.cNewNodes = pyo.Constraint(model.NODE,model.STAGE,
                                          rule=newNodes_rule)
          
        # Generator output limitations
        def maxPgen_rule(model,g,t,h):
            cap = model.genCapacity[g]
            if h>1:
                cap += model.genCapacity2[g]
            for x in range(h):
                cap += model.genNewCapacity[g,x+1]
            expr = model.generation[g,t,h] <= (
                model.genCapacityProfile[g,t] * cap)
            return expr
        model.cMaxPgen = pyo.Constraint(model.GEN,model.TIME,model.STAGE,
                                        rule=maxPgen_rule)
        
        # Generator maximum average output (energy sum) 
        # (e.g. for hydro with storage)
        def maxEnergy_rule(model,g,h):
            cap = model.genCapacity[g]
            if h>1:
                cap += model.genCapacity2[g]
            for x in range(h):
                cap += model.genNewCapacity[g,x+1]
            if model.genPAvg[g]>0:
                expr = (sum(model.generation[g,t,h] for t in model.TIME) 
                            <= (model.genPAvg[g]*cap*len(model.TIME)))
            else:
                expr = pyo.Constraint.Skip
            return expr
        model.cMaxEnergy = pyo.Constraint(model.GEN,model.STAGE,
                                               rule=maxEnergy_rule)


        # Emissions restriction per country/load
        # TODO: deal with situation when no emission cap has been given (-1)
        def emissionCap_rule(model,a,h):
            if model.CO2price > 0:
                expr = 0
                for n in model.NODE:
                    if model.nodeArea[n]==a:
                        expr += sum(model.generation[g,t,h]*model.genTypeEmissionRate[model.genType[g]]*model.samplefactor[t]
                                    for t in model.TIME for g in model.GEN 
                                    if model.genNode[g]==n)
                expr = (expr <= sum(model.emissionCap[c] 
                    for c in model.LOAD if model.nodeArea[model.demNode[c]]==a))
            else:
                expr = pyo.Constraint.Skip
            return expr 
        model.cEmissionCap = pyo.Constraint(model.AREA,model.STAGE,
                                             rule=emissionCap_rule)


        # Power balance in nodes : gen+demand+flow into node=0
        def powerbalance_rule(model,n,t,h):
            expr = 0
            # flow of power into node (subtrating losses)
            for j in model.BRANCH:
                if model.branchNodeFrom[j]==n:
                    # branch out of node
                    typ = model.branchType[j]
                    dist = model.branchDistance[j]
                    expr += -model.branchFlow12[j,t,h]
                    expr += model.branchFlow21[j,t,h] * (1-(
                                model.branchLossfactor[typ,'fix']
                                +model.branchLossfactor[typ,'slope']*dist))
                if model.branchNodeTo[j]==n:
                    # branch into node
                    typ = model.branchType[j]
                    dist = model.branchDistance[j]
                    expr += model.branchFlow12[j,t,h] * (1-(
                                model.branchLossfactor[typ,'fix']
                                +model.branchLossfactor[typ,'slope']*dist))
                    expr += -model.branchFlow21[j,t,h] 

            # generated power 
            for g in model.GEN:
                if model.genNode[g]==n:
                    expr += model.generation[g,t,h]
                    
            # load shedding
            expr += model.loadShed[n,t,h]

            # consumed power
            for c in model.LOAD:
                if model.demNode[c]==n:
                    expr += -model.demandAvg[c]*model.demandProfile[c,t]
            
            expr = (expr == 0)
            if ((type(expr) is bool) and (expr==True)):
                # Trivial constraint
                expr = pyo.Constraint.Skip
            return expr
        model.cPowerbalance = pyo.Constraint(model.NODE,model.TIME,model.STAGE,
                                             rule=powerbalance_rule)
        
        # COST PARAMETERS ############
        def costBranch(model,b,var_num,var_cap, stage):
            b_cost = 0
            typ = model.branchType[b]
            b_cost += (model.branchtypeCost[typ,'B']
                        *var_num[b,stage])
            b_cost += (model.branchtypeCost[typ,'Bd']
                        *model.branchDistance[b]
                        *var_num[b,stage])
            b_cost += (model.branchtypeCost[typ,'Bdp']
                        *model.branchDistance[b]
                        *var_cap[b,stage])
            
            #endpoints offshore (N=1) or onshore (N=0) ?
            N1 = model.branchOffshoreFrom[b]
            N2 = model.branchOffshoreTo[b]
            for N in [N1,N2]:
                b_cost += N*(model.branchtypeCost[typ,'CS']
                            *var_num[b,stage]
                        +model.branchtypeCost[typ,'CSp']
                        *var_cap[b,stage])            
                b_cost += (1-N)*(model.branchtypeCost[typ,'CL']
                            *var_num[b,stage]
                        +model.branchtypeCost[typ,'CLp']
                        *var_cap[b,stage])
            
            return model.branchCostScale[b]*b_cost

        def costNode(model,n,var_num,stage):
            n_cost = 0
            N = model.nodeOffshore[n]
            n_cost += N*(model.nodetypeCost[model.nodeType[n],'S']
                        *var_num[n,stage])
            n_cost += (1-N)*(model.nodetypeCost[model.nodeType[n],'L']
                        *var_num[n,stage])
            return model.nodeCostScale[n]*n_cost
            
        def costGen(model,g,var_cap,stage):
            g_cost = 0
            typ = model.genType[g]
            g_cost += model.genTypeCost[typ]*var_cap[g,stage]
            return model.genCostScale[g]*g_cost



        # OBJECTIVE ##############################################################
        model.investmentCost = pyo.Var(model.STAGE, within=pyo.Reals) 
        model.opCost = pyo.Var(model.STAGE, within=pyo.Reals)
        def investmentCost_rule(model,stage):
            """Investment cost, including lifetime O&M costs (NPV)"""
            investment = 0
            omcost = 0
            salvagefactor = (int(stage-1)*model.stage2TimeDelta/model.financeYears)*(
                    1/((1+model.financeInterestrate)
                    **(model.financeYears-model.stage2TimeDelta*int(stage-1))))
            discount_t0 = (1/((1+model.financeInterestrate)
                            **(model.stage2TimeDelta*int(stage-1))))
            # add branch, node and generator investment costs:
            for b in model.BRANCH:
                investment += costBranch(model,b,
                                   model.branchNewCables,
                                   model.branchNewCapacity,stage)
            for n in model.NODE:
                investment += costNode(model,n,model.newNodes,stage)            
            for g in model.GEN:
                investment += costGen(model, g,model.genNewCapacity,stage)*(
                    annuityfactor(model.financeInterestrate,model.financeYears)
                    -annuityfactor(model.financeInterestrate,int(stage-1)*model.stage2TimeDelta))            
            # add O&M costs:
            omcost = investment * model.omRate * (
                annuityfactor(model.financeInterestrate,model.financeYears)
                -annuityfactor(model.financeInterestrate,int(stage-1)*model.stage2TimeDelta))
            expr = investment + omcost 
            expr -= expr*salvagefactor
            expr = expr*discount_t0
            return model.investmentCost[stage] == expr
        model.cInvestmentCost = pyo.Constraint(model.STAGE,rule=investmentCost_rule)
        
        
        def opCost_rule(model, stage):
            """Operational costs: cost of gen, load shed (NPV)"""
            opcost = 0
            discount_t0 = (1/((1+model.financeInterestrate)
                **(model.stage2TimeDelta*int(stage-1))))
            
            opcost = sum(model.generation[i,t,stage]*model.samplefactor[t]*(
                        model.genCostAvg[i]*model.genCostProfile[i,t]
                        +model.genTypeEmissionRate[model.genType[i]]*model.CO2price)
                        for i in model.GEN for t in model.TIME)
            opcost += sum(model.loadShed[n,t,stage]*model.VOLL
                            for n in model.NODE for t in model.TIME)
            if stage == len(model.STAGE):
                opcost = opcost*(annuityfactor(model.financeInterestrate,model.financeYears)
                    - annuityfactor(model.financeInterestrate,int(stage-1)*model.stage2TimeDelta))
            else:
                opcost = opcost*annuityfactor(model.financeInterestrate,int(stage)*model.stage2TimeDelta)            
            expr = opcost*discount_t0
            return model.opCost[stage] == expr
        model.cOperationalCosts = pyo.Constraint(model.STAGE, rule=opCost_rule)
            
            

                                             
#        def firstStageCost_rule(model):
#            """Investment cost, including lifetime O&M costs (NPV)"""
#            investment = 0
#            stage=1
#
#            # add branch, node and generator investment costs:
#            for b in model.BRANCH:
#                investment += costBranch(model,b,
#                                   model.branchNewCables,
#                                   model.branchNewCapacity,stage)
#            for n in model.NODE:
#                investment += costNode(model,n,model.newNodes,stage)            
#            for g in model.GEN:
#                investment += costGen(model, g,model.genNewCapacity,stage)
#
#            # add O&M costs:
#            omcost = investment * model.omRate * annuityfactor(
#                            model.financeInterestrate,
#                            model.financeYears)
#            expr = investment + omcost                            
#            return   expr  
#        model.firstStageCost = pyo.Expression(rule=firstStageCost_rule)
#    
#        def secondStageCost_rule(model):
#            """Operational costs: cost of gen, load shed (NPV)"""
#            opcost1 = 0
#            opcost2 = 0
#            investment = 0
#            omcost = 0
#            if len(model.STAGE)<2:
#                stage = 1
#                opcost1 = sum(model.generation[i,t,stage]*model.samplefactor[t]*(
#                            model.genCostAvg[i]*model.genCostProfile[i,t]
#                            +model.genTypeEmissionRate[model.genType[i]]*model.CO2price)
#                            for i in model.GEN for t in model.TIME)
#                opcost1 += sum(model.loadShed[n,t,stage]*model.VOLL
#                                for n in model.NODE for t in model.TIME)
#                opcost1 = opcost1*annuityfactor(model.financeInterestrate,
#                                              model.financeYears)
#            else:
#                stage=2
#                # Operational costs phase 1 (if stage2DeltaTime>0)
#                opcost1 = sum(model.generation[i,t,stage-1]*model.samplefactor[t]*(
#                                model.genCostAvg[i]*model.genCostProfile[i,t]
#                                +model.genTypeEmissionRate[model.genType[i]]*model.CO2price)
#                                for i in model.GEN for t in model.TIME)
#                opcost1 += sum(model.loadShed[n,t,stage-1]*model.VOLL
#                                for n in model.NODE for t in model.TIME)
#                opcost1 = opcost1*annuityfactor(model.financeInterestrate,
#                                              model.stage2TimeDelta)
#                                              
#                # Operational costs phase 2 (disounted)
#                opcost2 = sum(model.generation[i,t,stage]*model.samplefactor[t]*(
#                                model.genCostAvg[i]*model.genCostProfile[i,t]
#                                +model.genTypeEmissionRate[model.genType[i]]*model.CO2price)
#                                for i in model.GEN for t in model.TIME)    
#                opcost2 += sum(model.loadShed[n,t,stage]*model.VOLL
#                                for n in model.NODE for t in model.TIME)
#                opcost2 = opcost2*(annuityfactor(model.financeInterestrate,
#                                   model.financeYears)
#                                   -annuityfactor(model.financeInterestrate,
#                                      model.stage2TimeDelta)
#                                      )
#                
#                # 2nd stage investment costs
#                for b in model.BRANCH:
#                    investment += costBranch(model,b,
#                                       model.branchNewCables,
#                                       model.branchNewCapacity,stage)
#                for n in model.NODE:
#                    investment += costNode(model,n,model.newNodes,stage)            
#                for g in model.GEN:
#                    investment += costGen(model, g,model.genNewCapacity,stage)
#                #discount back to t=0?
#                investment = investment*(1/((1+model.financeInterestrate)**model.stage2TimeDelta))
#    
#                # add O&M costs (NPV of lifetime costs)
#                omcost = investment*model.omRate*(
#                    annuityfactor(model.financeInterestrate,model.financeYears)
#                    -annuityfactor(model.financeInterestrate,model.stage2TimeDelta))
#                
#                #subtract estimated salvage value of investments with remaining lifetime
#                investment -= investment*(model.stage2TimeDelta/model.financeYears)*(
#                    1/((1+model.financeInterestrate)**(model.financeYears-model.stage2TimeDelta)))
#                    
#            expr = opcost1 + opcost2 + investment + omcost         
#            return expr
#        model.secondStageCost = pyo.Expression(rule=secondStageCost_rule)
#    
#        def total_Cost_Objective_rule(model):
#            return model.firstStageCost + model.secondStageCost
#        model.OBJ = pyo.Objective(rule=total_Cost_Objective_rule, 
#                                  sense=pyo.minimize)
        
        def total_Cost_Objective_rule(model):
            investment = pyo.summation(model.investmentCost)
            operation = pyo.summation(model.opCost)
            return investment + operation
        model.OBJ = pyo.Objective(rule=total_Cost_Objective_rule,
                                  sense=pyo.minimize)
        
    
        return model

        

    def _offshoreBranch(self,grid_data):
        '''find out whether branch endpoints are offshore or onshore
        
        Returns 1 for offshore and 0 for onsore from/to endpoints
        '''
        d={'from':[],'to':[]}
        
        d['from'] = [grid_data.node[grid_data.node['id']==n]['offshore']
                    .tolist()[0] for n in grid_data.branch['node_from']]
        d['to'] = [grid_data.node[grid_data.node['id']==n]['offshore']
                    .tolist()[0] for n in grid_data.branch['node_to']]
        return d

        
    def createConcreteModel(self,dict_data):
        """Create Concrete Pyomo model for PowerGIM
        
        Parameters
        ----------
        dict_data : dictionary
            dictionary containing the model data. This can be created with
            the createModelData(...) method
        
        Returns
        -------
            Concrete pyomo model
        """

        concretemodel = self.abstractmodel.create_instance(data=dict_data,
                               name="PowerGIM Model",
                               namespace='powergim')
        return concretemodel


    def createModelData(self,grid_data,datafile,
                        maxNewBranchNum, maxNewBranchCap):
        '''Create model data in dictionary format

        Parameters
        ----------
        grid_data : powergama.GridData object
            contains grid model
        datafile : string
            name of XML file containing additional parameters
        maxNewBranchNum : int
            upper limit on parallel branches to consider (e.g. 10)
        maxNewBranchCap : float (MW)
            upper limit on new capacity to consider (e.g. 10000)
        
        Returns
        --------
        dictionary with pyomo data (in pyomo format)
        '''
        
        branch_distances = grid_data.branchDistances()
        
        #to see how the data format is:        
        #data = pyo.DataPortal(model=self.abstractmodel)
        #data.load(filename=datafile)
        
        di = {}
        #Sets:
        di['NODE'] = {None: grid_data.node['id'].tolist() }
        di['BRANCH'] = {None: grid_data.branch.index.tolist() }
        di['GEN'] = {None: grid_data.generator.index.tolist() }
        di['LOAD'] = {None: grid_data.consumer.index.tolist() }
        di['AREA'] = {None: grid_data.getAllAreas() }
        di['TIME'] = {None: grid_data.timerange}
        #di['STAGE'] = {None: grid_data.branch.expand[grid_data.branch['expand']>0].unique().tolist()}
        
        br_expand1 = grid_data.branch[
                        grid_data.branch['expand']==1].index.tolist()
        br_expand2 = grid_data.branch[
                        grid_data.branch['expand']==2].index.tolist()
        gen_expand1 = grid_data.generator[
                        grid_data.generator['expand']==1].index.tolist()
        gen_expand2 = grid_data.generator[
                        grid_data.generator['expand']==2].index.tolist()
        # Convert from numpy.int64 (pandas) to int in order to work with PySP
        # (pprint function error otherwise)
        br_expand1 = [int(i) for i in br_expand1]
        br_expand2 = [int(i) for i in br_expand2]
        gen_expand1 = [int(i) for i in gen_expand1]
        gen_expand2 = [int(i) for i in gen_expand2]
        # Determine which nodes should be considered upgraded in each stage,
        # depending on whether any generators or branches are connected
        node_expand1=[]
        node_expand2=[]
        for n in grid_data.node['id'][grid_data.node['existing']==0]:
            if (n in grid_data.generator['node'][grid_data.generator['expand']==1].tolist()
                or n in grid_data.branch['node_to'][grid_data.branch['expand']==1].tolist() 
                or n in grid_data.branch['node_from'][grid_data.branch['expand']==1].tolist()):
                #stage one generator  or branch expansion connected to node
                node_expand1.append(n)
            if (n in grid_data.generator['node'][grid_data.generator['expand']==2].tolist()
                or n in grid_data.branch['node_to'][grid_data.branch['expand']==2].tolist() 
                or n in grid_data.branch['node_from'][grid_data.branch['expand']==2].tolist()):
                #stage two generator or branch expansion connected to node
                node_expand2.append(n)
#        node_expand1 = grid_data.node[
#                        grid_data.node['expand1']==1].index.tolist()
#        node_expand2 = grid_data.node[
#                        grid_data.node['expand2']==2].index.tolist()
        
        di['BRANCH_EXPAND1'] = {None: br_expand1}
        di['BRANCH_EXPAND2'] = {None: br_expand2}
        di['GEN_EXPAND1'] = {None:gen_expand1}
        di['GEN_EXPAND2'] = {None:gen_expand2}
        di['NODE_EXPAND1'] = {None:node_expand1}
        di['NODE_EXPAND2'] = {None:node_expand2}
        
        #Parameters:
        di['maxNewBranchNum'] = {None: maxNewBranchNum}
        di['samplefactor'] = {}
        if hasattr(grid_data.profiles, 'frequency'):
            di['samplefactor'] = grid_data.profiles['frequency']
        else:
            for t in grid_data.timerange:
                di['samplefactor'][t] = self._HOURS_PER_YEAR/len(grid_data.timerange)
        di['nodeOffshore'] = {}
        di['nodeType'] = {}
        di['nodeExistingNumber'] = {}
        di['nodeCostScale']={}
        di['nodeArea']={}
        for k,row in grid_data.node.iterrows():
            n=grid_data.node['id'][k]
            #n=grid_data.node.index[k] #or simply =k
            di['nodeOffshore'][n] = row['offshore']
            di['nodeType'][n] = row['type']
            di['nodeExistingNumber'][n] = row['existing']
            di['nodeCostScale'][n] = row['cost_scaling']
            di['nodeArea'][n] = row['area']
            
        di['branchExistingCapacity'] = {}
        di['branchExistingCapacity2'] = {}
        di['branchExpand'] = {}
        di['branchExpand2'] = {}
        di['branchDistance'] = {}
        di['branchType'] = {}
        di['branchCostScale'] = {}
        di['branchOffshoreFrom'] = {}
        di['branchOffshoreTo'] = {}
        di['branchNodeFrom'] = {}
        di['branchNodeTo'] = {}
        di['branchMaxNewCapacity'] = {}
        offsh = self._offshoreBranch(grid_data)
        for k,row in grid_data.branch.iterrows():
            di['branchExistingCapacity'][k] = row['capacity']
            di['branchExistingCapacity2'][k] = row['capacity2']
            if row['max_newCap'] >0:
                di['branchMaxNewCapacity'][k] = row['max_newCap']
            else:
                di['branchMaxNewCapacity'][k] = maxNewBranchCap
            di['branchExpand'][k] = row['expand']
            di['branchExpand2'][k] = row['expand2']
            if row['distance'] >= 0:
                di['branchDistance'][k] = row['distance']
            else:
                di['branchDistance'][k] = branch_distances[k]                    
            di['branchType'][k] = row['type']
            di['branchCostScale'][k] = row['cost_scaling']
            di['branchOffshoreFrom'][k] = offsh['from'][k]
            di['branchOffshoreTo'][k] = offsh['to'][k]
            di['branchNodeFrom'][k] = row['node_from']
            di['branchNodeTo'][k] = row['node_to']
            
        di['genCapacity']={}
        di['genCapacity2']={}
        di['genCapacityProfile']={}
        di['genNode']={}
        di['genCostAvg'] = {}
        di['genCostProfile'] = {}
        di['genPAvg'] = {}
        di['genExpand'] = {}
        di['genExpand2'] = {}
        di['genNewCapMax'] = {}
        di['genType'] = {}
        di['genCostScale'] = {}
        for k,row in grid_data.generator.iterrows():
            di['genCapacity'][k] = row['pmax']
            di['genCapacity2'][k] = row['pmax2']
            di['genNode'][k] = row['node']
            di['genCostAvg'][k] = row['fuelcost']
            di['genPAvg'][k] = row['pavg']
            di['genExpand'][k] = row['expand']
            di['genExpand2'][k] = row['expand2']
            di['genNewCapMax'][k] = row['p_maxNew']
            di['genType'][k] = row['type']
            di['genCostScale'][k] = row['cost_scaling']
            ref = row['fuelcost_ref']
            ref2 = row['inflow_ref']
            for i,t in enumerate(grid_data.timerange):
                di['genCostProfile'][(k,t)] = grid_data.profiles[ref][i]
                di['genCapacityProfile'][(k,t)] = (grid_data.profiles[ref2][i]
                            * row['inflow_fac'])
           
        di['demandAvg'] = {}
        di['demandProfile'] ={}
        di['demNode'] = {}
        di['emissionCap'] = {}
        for k,row in grid_data.consumer.iterrows():
            di['demNode'][k] = row['node']
            di['demandAvg'][k] = row['demand_avg']
            di['emissionCap'][k] = row['emission_cap']
            ref = row['demand_ref']
            for i,t in enumerate(grid_data.timerange):
                di['demandProfile'][(k,t)] = grid_data.profiles[ref][i]
        

        # Read input data from XML file
        import xml
        tree=xml.etree.ElementTree.parse(datafile)
        root = tree.getroot()
        
        di['NODETYPE'] = {None:[]}
        di['nodetypeCost'] = {}
        for i in root.findall('./nodetype/item'):
            name = i.attrib['name']
            di['NODETYPE'][None].append(name)
            di['nodetypeCost'][(name,'L')] = float(i.attrib['L'])
            di['nodetypeCost'][(name,'S')] = float(i.attrib['S'])

        di['BRANCHTYPE'] = {None:[]}
        di['branchtypeCost'] = {}
        di['branchtypeMaxCapacity'] = {}
        di['branchLossfactor'] = {}
        for i in root.findall('./branchtype/item'):
            name = i.attrib['name']
            di['BRANCHTYPE'][None].append(name)
            di['branchtypeCost'][(name,'B')] = float(i.attrib['B'])
            di['branchtypeCost'][(name,'Bd')] = float(i.attrib['Bd'])
            di['branchtypeCost'][(name,'Bdp')] = float(i.attrib['Bdp'])
            di['branchtypeCost'][(name,'CL')] = float(i.attrib['CL'])
            di['branchtypeCost'][(name,'CLp')] = float(i.attrib['CLp'])
            di['branchtypeCost'][(name,'CS')] = float(i.attrib['CS'])
            di['branchtypeCost'][(name,'CSp')] = float(i.attrib['CSp'])
            di['branchtypeMaxCapacity'][name] = float(i.attrib['maxCap'])
            di['branchLossfactor'][(name,'fix')] = float(i.attrib['lossFix'])
            di['branchLossfactor'][(name,'slope')] = float(i.attrib['lossSlope'])
                                                        
        di['GENTYPE'] = {None:[]}
        di['genTypeCost'] = {}
        di['genTypeEmissionRate'] = {}
        for i in root.findall('./gentype/item'):
            name = i.attrib['name']
            di['GENTYPE'][None].append(name)
            di['genTypeCost'][name] = float(i.attrib['CX']) 
            di['genTypeEmissionRate'][name] = float(i.attrib['CO2'])                                               
        
        for i in root.findall('./parameters'):
            di['financeInterestrate'] = {None: 
                float(i.attrib['financeInterestrate'])}
            di['financeYears'] = {None: 
                float(i.attrib['financeYears'])}
            di['omRate'] = {None: 
                float(i.attrib['omRate'])}
            di['CO2price'] = {None: 
                float(i.attrib['CO2price'])}
            di['VOLL'] = {None: 
                float(i.attrib['VOLL'])}
            di['stage2TimeDelta'] = {None: 
                float(i.attrib['stage2TimeDelta'])}
            di['STAGE'] = {None: 
                list(range(1,int(i.attrib['stages'])+1))}

        return {'powergim':di}

        
    def writeStochasticProblem(self,path,dict_data):
        '''create input files for solving stochastic problem
        
        Parameters
        ----------
        path : string
            Where to put generated files
        dict_data : dictionary
            Pyomo data model in dictionary format. Output from 
            createModelData method
            
        Returns
        -------
        string that can be written to .dat file (reference model data)
        '''
        
        NL="\n"
        TAB="\t"
        dat_str = "#PowerGIM data file"+NL   
        str_set=""
        str_param=""
        str_sprm=""
        
        for key,val in dict_data['powergim'].items():
            v = getattr(self.abstractmodel,key)
            
            if type(v)==pyo.base.sets.SimpleSet:
                str_set += "set " + key + " := "
                for x in val[None]:
                    str_set += str(x) + " "
                str_set += ";" + NL
                
            elif type(v)==pyo.base.param.IndexedParam:
                print("PARAM: ",v)
                str_param += "param " + key + ":= " + NL
                for k2,v2 in val.items():
                    str_param += TAB
                    if isinstance(k2,tuple):
                        #multiple keys (table data)
                        for ki in k2:
                            str_param += str(ki) + TAB
                    else:
                        #single key (list data)
                        str_param += str(k2) + TAB
                    str_param += str(v2) + NL
                str_param += TAB+";"+NL
                
            elif type(v)==pyo.base.param.SimpleParam:
                # single value data
                str_sprm += "param " + key + " := " + str(val[None]) + ";" + NL
                
            else:
                print("Unknown data  ",key,v,type(v))
                raise Exception("Unknown data")
            
        dat_str += NL + str_set + NL + str_sprm + NL + str_param    
        
        #scenario structure data file:
        #root node scenario data:
        with open("{}/RootNode.dat".format(path), "w") as text_file:
            text_file.write(dat_str)
        print("Root node data written to {}/RootNode.dat".format(path))
        
        return dat_str
        
        
    def createScenarioTreeModel(self,num_scenarios,probabilities=None):
        '''Generate model instance with data. Alternative to .dat files
        
        Parameters
        ----------
        num_scenarios : int
            number of scenarios. Each with the same probability
        probabilities : list of float
            probabilities of each scenario (must sum to 1). Number of elements
            determine number of scenarios
        
        Returns
        -------
        PySP 2-stage scenario tree model
        
        This method may be called by "pysp_scenario_tree_model_callback()" in
        the model input file instead of using input .dat files
        '''
        
        if probabilities is None:
            # equal probability:
            probabilities = [1/num_scenarios]*num_scenarios
        #if probabilities is None:
        #    st_model = tsm.CreateConcreteTwoStageScenarioTreeModel(
        #                        num_scenarios)

        G = networkx.DiGraph() 
        G.add_node("root")
        for i in range(len(probabilities)):
            G.add_edge("root","Scenario{}".format(i+1),
                       probability=probabilities[i])
        stage_names=['Stage1','Stage2']

        st_model = tsm.ScenarioTreeModelFromNetworkX(G,
                         edge_probability_attribute="probability",
                         stage_names=stage_names)
    
        first_stage = st_model.Stages.first()
        second_stage = st_model.Stages.last()
    
        # First Stage
        st_model.StageCost[first_stage] = 'firstStageCost'
        st_model.StageVariables[first_stage].add('branchNewCables')
        st_model.StageVariables[first_stage].add('branchNewCapacity')
        st_model.StageVariables[first_stage].add('newNodes')
        st_model.StageVariables[first_stage].add('genNewCapacity')
    
        # Second Stage
        st_model.StageCost[second_stage] = 'secondStageCost'
        st_model.StageVariables[second_stage].add('generation')
        st_model.StageVariables[second_stage].add('branchFlow12')
        st_model.StageVariables[second_stage].add('branchFlow21')
        st_model.StageVariables[second_stage].add('genNewCapacity')
        st_model.StageVariables[second_stage].add('branchNewCables')
        st_model.StageVariables[second_stage].add('branchNewCapacity')
        st_model.StageVariables[second_stage].add('newNodes')
            
        st_model.ScenarioBasedData=False
                
        return st_model
        
        
    def computeBranchCongestionRent(self, model, b, stage=1):
        '''
        Compute annual congestion rent for a given branch
        '''
        # TODO: use nodal price, not area price.
        N1 = model.branchNodeFrom[b]
        N2 = model.branchNodeTo[b]

        area1 = model.nodeArea[N1]
        area2 = model.nodeArea[N2]
        
        flow = []
        deltaP = []
        
        for t in model.TIME:
            deltaP.append(abs(self.computeAreaPrice(model, area1, t,stage) 
                         - self.computeAreaPrice(model, area2, t,stage))*model.samplefactor[t])
            flow.append(model.branchFlow21[b,t,stage].value + model.branchFlow12[b,t,stage].value)
        
        return sum(deltaP[i]*flow[i] for i in range(len(deltaP)))

    def computeCostBranch(self,model,b,stage,include_om=False):
        '''Investment cost of single branch
        
        corresponds to  firstStageCost in abstract model'''
        
        ar = 1
        br_num=0
        br_cap=0
        b_cost = 0
        if stage==1:
            ar = annuityfactor(model.financeInterestrate,model.financeYears)
        elif stage==2:
            ar = (annuityfactor(model.financeInterestrate,model.financeYears)
                  -annuityfactor(model.financeInterestrate,
                                 model.stage2TimeDelta))
        br_num += model.branchNewCables[b,stage].value
        br_cap += model.branchNewCapacity[b,stage].value
        typ = model.branchType[b]
        b_cost += (model.branchtypeCost[typ,'B']
                    *br_num)
        b_cost += (model.branchtypeCost[typ,'Bd']
                    *model.branchDistance[b]*br_num)
        b_cost += (model.branchtypeCost[typ,'Bdp']
                    *model.branchDistance[b]*br_cap)
        #endpoints offshore (N=1) or onshore (N=0) ?
        N1 = model.branchOffshoreFrom[b]
        N2 = model.branchOffshoreTo[b]
        for N in [N1,N2]:
            b_cost += N*(model.branchtypeCost[typ,'CS']*br_num
                        +model.branchtypeCost[typ,'CSp']*br_cap)            
            b_cost += (1-N)*(model.branchtypeCost[typ,'CL']*br_num
                        +model.branchtypeCost[typ,'CLp']*br_cap)
        cost = model.branchCostScale[b]*b_cost
        if include_om:
            cost = cost*(1 + model.omRate * ar)
        return cost

    def computeCostNode(self,model,n,include_om=False):
        '''Investment cost of single node
        
        corresponds to cost in abstract model'''
        
        # node may be expanded in stage 1 or stage 2, but will never be 
        # expanded in both
        
        ar = 1
        n_num = 0
        for s in model.STAGE:
            if s<2:
                n_num = model.newNodes[n,s].value
                ar = (annuityfactor(model.financeInterestrate,model.financeYears))
            else:
                n_num = model.newNodes[n,s-1].value+model.newNodes[n,s].value
                ar = (annuityfactor(model.financeInterestrate,model.financeYears)
                      -annuityfactor(model.financeInterestrate,
                                     model.stage2TimeDelta))
        n_cost = 0
        N = model.nodeOffshore[n]
        n_cost += N*(model.nodetypeCost[model.nodeType[n],'S']*n_num)
        n_cost += (1-N)*(model.nodetypeCost[model.nodeType[n],'L']*n_num)
        cost = model.nodeCostScale[n]*n_cost
        if include_om:
            cost = cost*(1 + model.omRate * ar)
        return cost


    def computeCostGenerator(self,model,g,stage,include_om=False):
        '''Investment cost of generator
        '''
        ar = 1
        g_cap = 0
        if stage==1:
            ar = annuityfactor(model.financeInterestrate,model.financeYears)
        elif stage==2:
            ar = (annuityfactor(model.financeInterestrate,model.financeYears)
                      -annuityfactor(model.financeInterestrate,
                                     model.stage2TimeDelta))
        g_cap = model.genNewCapacity[g,stage].value
        typ = model.genType[g]
        cost = model.genTypeCost[typ]*g_cap
        if include_om:
            cost = cost*(1 + model.omRate * ar)
        return cost
                
                
    def computeGenerationCost(self,model,g,stage):
        '''compute NPV cost of generation (+ CO2 emissions)
        
        This corresponds to secondStageCost in abstract model        
        '''
        ar = 1
        if stage == 1:
            gen = model.generation
            ar = annuityfactor(model.financeInterestrate,
                               model.stage2TimeDelta)
        elif stage==2:
            gen = model.generation
            ar = (
                annuityfactor(model.financeInterestrate,model.financeYears)
                -annuityfactor(model.financeInterestrate,model.stage2TimeDelta)
                )
        expr = sum(gen[g,t,stage].value*model.samplefactor[t]*
                    model.genCostAvg[g]*model.genCostProfile[g,t] 
                     for t in model.TIME)
        expr2 = sum(gen[g,t,stage].value*model.samplefactor[t]*
                            model.genTypeEmissionRate[model.genType[g]]
                            for t in model.TIME)
        expr2 = expr2*model.CO2price.value
        # lifetime cost
        expr = (expr+expr2)*ar
        return expr
     
                
    def computeDemand(self,model,c,t):
        '''compute demand at specified load ant time'''
        return model.demandAvg[c]*model.demandProfile[c,t]
    
    
    
    def computeCurtailment(self, model, g, t, stage):
        '''compute curtailment [MWh] per generator per hour'''
        cur = 0
        gen_max = 0
        if stage == 1:
            gen_max = model.genCapacity[g] + model.genNewCapacity[g,stage].value
            cur = gen_max*model.genCapacityProfile[g,t] - model.generation[g,t,stage].value
        if stage == 2:
            gen_max = (model.genCapacity[g] + model.genCapacity2[g] 
                        +model.genNewCapacity[g,stage-1].value
                        +model.genNewCapacity[g,stage].value)
            cur = gen_max*model.genCapacityProfile[g,t] - model.generation[g,t,stage].value
        return cur
        
        

        
    def computeAreaEmissions(self,model,c, stage, cost=False):
        '''compute total emissions from a load/country'''
        # TODO: ensure that all nodes are mapped to a country/load
        n = model.demNode[c]
        expr = 0
        gen=model.generation
        if stage==1:
            ar = annuityfactor(model.financeInterestrate,model.stage2TimeDelta)
        elif stage==2:
            ar = (annuityfactor(model.financeInterestrate,model.financeYears)
                -annuityfactor(model.financeInterestrate,model.stage2TimeDelta))
                
        for g in model.GEN:
            if model.genNode[g]==n:
                expr += sum(gen[g,t,stage].value*model.samplefactor[t]*
                            model.genTypeEmissionRate[model.genType[g]]
                            for t in model.TIME)
        if cost:
            expr = expr * model.CO2price.value * ar
        return expr
        
                                
    def computeAreaRES(self, model,j,stage, shareof):
        '''compute renewable share of demand or total generation capacity'''
        node = model.demNode[j]
        area = model.nodeArea[node]
        Rgen = 0
        costlimit_RES=1 # limit for what to consider renewable generator
        gen_p=model.generation
        gen = 0
        dem = sum(model.demandAvg[j]*model.demandProfile[j,t] for t in model.TIME)
        for g in model.GEN:
            if model.nodeArea[model.genNode[g]]==area:
                if model.genCostAvg[g] <= costlimit_RES:
                    Rgen += sum(gen_p[g,t,stage].value for t in model.TIME)
                else:
                    gen += sum(gen_p[g,t,stage].value for t in model.TIME)

        if shareof=='dem':
           return Rgen/dem
        elif shareof=='gen':
           return Rgen/(gen+Rgen)
        else:
           print('Choose shareof dem or gen')

    
    def computeAreaPrice(self, model, area, t, stage):
        '''cumpute the approximate area price based on max marginal cost'''
        mc = []
        for g in model.GEN:
            gen = model.generation[g,t,stage].value                
            if gen > 0:
                if model.nodeArea[model.genNode[g]]==area:
                    mc.append(model.genCostAvg[g]*model.genCostProfile[g,t]
                                +model.genTypeEmissionRate[model.genType[g]]*model.CO2price.value)
        price = max(mc)
        return price

        
    def computeAreaWelfare(self, model, c, t, stage):
        '''compute social welfare for a given area and time step
        
        Returns: Welfare, ProducerSurplus, ConsumerSurplus, 
                 CongestionRent, IMport, eXport
        '''
        node = model.demNode[c]
        area = model.nodeArea[node]
        PS = 0; CS = 0; CR = 0; GC = 0; gen = 0; 
        dem = model.demandAvg[c]*model.demandProfile[c,t]
        price = self.computeAreaPrice(model, area, t, stage)
        #branch_capex = self.computeAreaCostBranch(model,c,include_om=True) #npv
        #gen_capex = self.computeAreaCostGen(model,c) #annualized
        
        #TODO: check phase1 vs phase2
        gen_p = model.generation
        flow12 = model.branchFlow12
        flow21 = model.branchFlow21

        for g in model.GEN:
            if model.nodeArea[model.genNode[g]]==area:
                gen += gen_p[g,t,stage].value
                GC += gen_p[g,t,stage].value*(
                    model.genCostAvg[g]*model.genCostProfile[g,t]
                    +model.genTypeEmissionRate[model.genType[g]]*model.CO2price.value)
        CS = (model.VOLL-price)*dem
        CC = price*dem
        PS = price*gen - GC
        if gen > dem:
            X = price*(gen-dem)
            IM = 0
            flow = []
            price2 = []
            for j in model.BRANCH:
                if (model.nodeArea[model.branchNodeFrom[j]]==area and
                    model.nodeArea[model.branchNodeTo[j]]!=area):
                        flow.append(flow12[j,t,stage].value)
                        price2.append(self.computeAreaPrice(model,
                                        model.nodeArea[model.branchNodeTo[j]],
                                        t,stage))
                if (model.nodeArea[model.branchNodeTo[j]]==area and
                    model.nodeArea[model.branchNodeFrom[j]]!=area):
                        flow.append(flow21[j,t,stage].value)
                        price2.append(self.computeAreaPrice(model,
                                        model.nodeArea[model.branchNodeFrom[j]],
                                        t,stage))
            CR = sum(flow[i]*(price2[i]-price) for i in range(len(flow)))/2
        elif gen < dem:
            X = 0
            IM = price*(dem-gen)
            flow = []
            price2 = []
            for j in model.BRANCH:
                if (model.nodeArea[model.branchNodeFrom[j]]==area and
                    model.nodeArea[model.branchNodeTo[j]]!=area):
                        flow.append(flow21[j,t,stage].value)
                        price2.append(self.computeAreaPrice(model,
                                        model.nodeArea[model.branchNodeTo[j]],
                                        t,stage))
                if (model.nodeArea[model.branchNodeTo[j]]==area and
                    model.nodeArea[model.branchNodeFrom[j]]!=area):
                        flow.append(flow12[j,t,stage].value)
                        price2.append(self.computeAreaPrice(model,
                                        model.nodeArea[model.branchNodeFrom[j]],
                                        t,stage))
            CR = sum(flow[i]*(price-price2[i]) for i in range(len(flow)))/2
        else:
            X = 0
            IM = 0
            flow = [0]
            price2 = [0]
            CR = 0
        W = PS + CS + CR
        return {'W':W, 'PS':PS, 'CS':CS, 'CC':CC, 'GC':GC, 'CR':CR, 'IM':IM, 'X':X}

            
    def computeAreaCostBranch(self,model,c,stage,include_om=False):
        '''Investment cost for branches connected to an given area'''
        node = model.demNode[c]
        area = model.nodeArea[node]
        cost = 0
        
        for b in model.BRANCH:
            if model.nodeArea[model.branchNodeTo[b]]==area:
                cost += self.computeCostBranch(model,b,stage,include_om)
            elif model.nodeArea[model.branchNodeFrom[b]]==area:
                cost += self.computeCostBranch(model,b,stage,include_om)
        
        # assume 50/50 cost sharing
        return cost/2
        
        
    def computeAreaCostGen(self,model,c):
        '''compute capital costs for new generator capacity'''
        node = model.demNode[c]
        area = model.nodeArea[node]
        gen_capex = 0
        
        for g in model.GEN:
            if model.nodeArea[model.genNode[g]]==area:
                typ = model.genType[g]
                gen_capex += model.genTypeCost[typ]*model.genNewCapacity[g].value*model.genCostScale[g]
                
        return gen_capex  
        
    def saveDeterministicResults(self,model,excel_file):
        '''export results to excel file
        
        Parameters
        ==========
        model : Pyomo model
            concrete instance of optimisation model
        excel_file : string
            name of Excel file to create
        
        '''
        df_branches = pd.DataFrame()
        df_nodes = pd.DataFrame()
        df_gen = pd.DataFrame()
        df_load = pd.DataFrame()
        # Specifying columns is not necessary, but useful to get the wanted 
        # ordering
        df_branches = pd.DataFrame(columns=['from','to','fArea','tArea','type',
                                           'existingCapacity','expand','newCables','newCapacity',
                                           'flow12avg_1','flow21avg_1',
                                           'existingCapacity2','expand2','newCables2','newCapacity2',
                                           'flow12avg_2', 'flow21avg_2',
                                           'cost_withOM','congestion_rent'])
        df_nodes = pd.DataFrame(columns=['num','area','newNodes1','newNodes2',
                                         'cost','cost_withOM'])
        df_gen = pd.DataFrame(columns=['num','node','area','type',
                                       'pmax','expand','newCapacity',
                                       'pmax2','expand2','newCapacity2'])
        df_load = pd.DataFrame(columns=['num','node','area','Pavg','Pmin','Pmax',
                                        'emissions','emissionCap', 'emission_cost',
                                        'price_avg','RES%dem','RES%gen', 'IM', 'EX',
                                        'CS', 'PS', 'CR', 'CAPEX', 'Welfare'])
        
        for j in model.BRANCH:
            df_branches.loc[j,'num'] = j
            df_branches.loc[j,'from'] = model.branchNodeFrom[j]
            df_branches.loc[j,'to'] = model.branchNodeTo[j]
            df_branches.loc[j,'fArea'] = model.nodeArea[model.branchNodeFrom[j]]
            df_branches.loc[j,'tArea'] = model.nodeArea[model.branchNodeTo[j]]
            df_branches.loc[j,'type'] = model.branchType[j]
            df_branches.loc[j,'existingCapacity'] = model.branchExistingCapacity[j]
            df_branches.loc[j,'expand'] = model.branchExpand[j]
            df_branches.loc[j,'existingCapacity2'] = model.branchExistingCapacity2[j]
            df_branches.loc[j,'expand2'] = model.branchExpand2[j]
            for s in model.STAGE:
                if s == 1:
                    df_branches.loc[j,'newCables'] = model.branchNewCables[j,s].value
                    df_branches.loc[j,'newCapacity'] = model.branchNewCapacity[j,s].value
                    df_branches.loc[j,'flow12avg_1'] = np.mean([
                        model.branchFlow12[(j,t,s)].value for t in model.TIME])
                    df_branches.loc[j,'flow21avg_1'] = np.mean([
                        model.branchFlow21[(j,t,s)].value for t in model.TIME])
                    cap1 = model.branchExistingCapacity[j] + model.branchNewCapacity[j,s].value  
                    df_branches.loc[j,'flow12%_1'] = (
                            df_branches.loc[j,'flow12avg_1']/cap1)
                    df_branches.loc[j,'flow21%_1'] = (
                            df_branches.loc[j,'flow21avg_1']/cap1)   
                elif s==2:
                    df_branches.loc[j,'newCables2'] = model.branchNewCables[j,s].value
                    df_branches.loc[j,'newCapacity2'] = model.branchNewCapacity[j,s].value
                    df_branches.loc[j,'flow12avg_2'] = np.mean([
                        model.branchFlow12[(j,t,s)].value for t in model.TIME])
                    df_branches.loc[j,'flow21avg_2'] = np.mean([
                        model.branchFlow21[(j,t,s)].value for t in model.TIME])
                    cap1 = model.branchExistingCapacity[j] + model.branchNewCapacity[j,s-1].value
                    cap2 = cap1 + model.branchExistingCapacity2[j] + model.branchNewCapacity[j,s].value
                    df_branches.loc[j,'flow12%_2'] = (
                            df_branches.loc[j,'flow12avg_2']/cap2)
                    df_branches.loc[j,'flow21%_2'] = (
                            df_branches.loc[j,'flow21avg_2']/cap2)                
            #branch costs
            df_branches.loc[j,'cost'] = sum(self.computeCostBranch(model,j,stage) for stage in model.STAGE)
            df_branches.loc[j,'cost_withOM'] = sum(self.computeCostBranch(
                        model,j,stage,include_om=True) for stage in model.STAGE)
            df_branches.loc[j,'congestion_rent'] = self.computeBranchCongestionRent(
                        model,j,stage=len(model.STAGE))*annuityfactor(model.financeInterestrate,model.financeYears)
        
        for j in model.NODE:
            df_nodes.loc[j,'num'] = j
            df_nodes.loc[j,'area'] = model.nodeArea[j]
            for s in model.STAGE:
                if s==1:
                    df_nodes.loc[j,'newNodes1'] = model.newNodes[j,s].value
                elif s==2:
                    df_nodes.loc[j,'newNodes2'] = model.newNodes[j,s].value
            df_nodes.loc[j,'cost'] = self.computeCostNode(model,j)
            df_nodes.loc[j,'cost_withOM'] = self.computeCostNode(model,j,
                include_om=True)
            
        
        for j in model.GEN:
            df_gen.loc[j,'num'] = j
            df_gen.loc[j,'area'] = model.nodeArea[model.genNode[j]]
            df_gen.loc[j,'node'] = model.genNode[j]
            df_gen.loc[j,'type'] = model.genType[j]
            df_gen.loc[j,'pmax'] = model.genCapacity[j]
            df_gen.loc[j,'pmax2'] = model.genCapacity2[j]
            df_gen.loc[j,'expand'] = model.genExpand[j]
            df_gen.loc[j,'expand2'] = model.genExpand2[j]
            df_gen.loc[j,'emission_rate'] = model.genTypeEmissionRate[model.genType[j]]
            for s in model.STAGE:
                if s==1:
                    df_gen.loc[j,'emission1'] = (model.genTypeEmissionRate[model.genType[j]]*sum(
                        model.generation[j,t,s].value*model.samplefactor[t] for t in model.TIME))
                    df_gen.loc[j,'Pavg1'] = np.mean([
                        model.generation[(j,t,s)].value for t in model.TIME])
                    df_gen.loc[j,'Pmin1'] = np.min([
                        model.generation[(j,t,s)].value for t in model.TIME])
                    df_gen.loc[j,'Pmax1'] = np.max([
                        model.generation[(j,t,s)].value for t in model.TIME])
                    df_gen.loc[j,'curtailed_avg1'] = np.mean([
                        self.computeCurtailment(model,j,t,stage=1) for t in model.TIME])
                    df_gen.loc[j,'newCapacity'] = model.genNewCapacity[j,s].value
                    df_gen.loc[j,'cost_NPV1'] = self.computeGenerationCost(model,j,stage=1)
                elif s==2:
                    df_gen.loc[j,'emission2'] = (model.genTypeEmissionRate[model.genType[j]]*sum(
                        model.generation[j,t,s].value*model.samplefactor[t] for t in model.TIME))
                    df_gen.loc[j,'Pavg2'] = np.mean([
                        model.generation[(j,t,s)].value for t in model.TIME])
                    df_gen.loc[j,'Pmin2'] = np.min([
                        model.generation[(j,t,s)].value for t in model.TIME])
                    df_gen.loc[j,'Pmax2'] = np.max([
                        model.generation[(j,t,s)].value for t in model.TIME])
                    df_gen.loc[j,'curtailed_avg2'] = np.mean([
                        self.computeCurtailment(model,j,t,stage=2) for t in model.TIME])
                    df_gen.loc[j,'newCapacity2'] = model.genNewCapacity[j,s].value
                    df_gen.loc[j,'cost_NPV2'] = self.computeGenerationCost(model,j,stage=2)
                
            df_gen.loc[j,'cost_investment'] = sum(self.computeCostGenerator(model,j,stage) for stage in model.STAGE)
            df_gen.loc[j,'cost_investment_withOM'] = sum(self.computeCostGenerator(model,j,stage,
                include_om=True) for stage in model.STAGE)

        print("TODO: powergim.saveDeterministicResults LOAD:"
                "only showing phase 2 (after 2nd stage investments)")
        stage=2
        def _n(n,p):
            return n+str(p)
            
        for j in model.LOAD:
            df_load.loc[j,'num'] = j
            df_load.loc[j,'node'] = model.demNode[j]
            df_load.loc[j,'area'] = model.nodeArea[model.demNode[j]]
            df_load.loc[j,'price_avg'] = np.mean(
                [self.computeAreaPrice(model,df_load.loc[j,'area'], t,stage=stage)
                for t in model.TIME])
            df_load.loc[j,'Pavg'] = np.mean([self.computeDemand(model,j,t)
                for t in model.TIME])
            df_load.loc[j,'Pmin'] = np.min([self.computeDemand(model,j,t)
                for t in model.TIME])
            df_load.loc[j,'Pmax'] = np.max([self.computeDemand(model,j,t)
                for t in model.TIME])
            df_load.loc[j,'emissionCap'] = model.emissionCap[j]
            df_load.loc[j,_n('emissions',stage)] = self.computeAreaEmissions(model,j,
                                                stage=stage)
            df_load.loc[j,_n('emission_cost',stage)] = self.computeAreaEmissions(model,j, 
                                                stage=stage,cost=True)
            df_load.loc[j,_n('RES%dem',stage)] = self.computeAreaRES(model,j,stage=stage,
                                                            shareof='dem')
            df_load.loc[j,_n('RES%gen',stage)] = self.computeAreaRES(model,j,stage=stage,
                                                            shareof='gen')
            df_load.loc[j,_n('Welfare',stage)] = sum(self.computeAreaWelfare(model,j,t,stage=stage)['W']*model.samplefactor[t]
                                            for t in model.TIME)
            df_load.loc[j,_n('PS',stage)] = sum(self.computeAreaWelfare(model,j,t,stage=stage)['PS']*model.samplefactor[t]
                                            for t in model.TIME)
            df_load.loc[j,_n('CS',stage)] = sum(self.computeAreaWelfare(model,j,t,stage=stage)['CS']*model.samplefactor[t]
                                            for t in model.TIME)
            df_load.loc[j,_n('CR',stage)] = sum(self.computeAreaWelfare(model,j,t,stage=stage)['CR']*model.samplefactor[t]
                                            for t in model.TIME)
            df_load.loc[j,_n('IM',stage)] = sum(self.computeAreaWelfare(model,j,t,stage=stage)['IM']*model.samplefactor[t]
                                            for t in model.TIME)
            df_load.loc[j,_n('EX',stage)] = sum(self.computeAreaWelfare(model,j,t,stage=stage)['X']*model.samplefactor[t]
                                            for t in model.TIME)
            df_load.loc[j,_n('CAPEX1',stage)] = self.computeAreaCostBranch(model,j,stage,
                                            include_om=False)
        
        df_cost = pd.DataFrame(columns=['value','unit'])
#        df_cost.loc['firstStageCost','value'] = (
#            pyo.value(model.firstStageCost)/10**9)
#        df_cost.loc['secondStageCost','value'] = (
#            pyo.value(model.secondStageCost)/10**9)
        df_cost.loc['newTransmission','value'] = sum(
            self.computeCostBranch(model,b,stage,include_om=True) for b in model.BRANCH for stage in model.STAGE)/10**9
        df_cost.loc['newGeneration','value'] = sum(
            self.computeCostGenerator(model,g,stage,include_om=True) for g in model.GEN for stage in model.STAGE)/10**9
        df_cost.loc['firstStageCost','unit'] = '10^9 EUR'
        df_cost.loc['secondStageCost','unit'] = '10^9 EUR'
        df_cost.loc['newTransmission','unit'] = '10^9 EUR'
        df_cost.loc['newGeneration','unit'] = '10^9 EUR'
            
        #model.solutions.load_from(results)
        #print('First stage costs: ', 
        #      pyo.value(model.firstStageCost)/10**9, 'bnEUR')
        #print('Second stage costs: ', 
        #      pyo.value(model.secondStageCost)/10**9, 'bnEUR')

        writer = pd.ExcelWriter(excel_file) 
        df_cost.to_excel(excel_writer=writer,sheet_name="cost") 
        df_branches.to_excel(excel_writer=writer,sheet_name="branches")     
        df_nodes.to_excel(excel_writer=writer,sheet_name="nodes") 
        df_gen.to_excel(excel_writer=writer,sheet_name="generation") 
        df_load.to_excel(excel_writer=writer,sheet_name="demand") 


    def extractResultingGridData(self,grid_data,
                                 model=None,file_ph=None,
                                 stage=1,scenario=None, newData=False):
        '''Extract resulting optimal grid layout from simulation results
        
        Parameters
        ==========
        grid_data : powergama.GridData
            grid data class
        model : Pyomo model
            concrete instance of optimisation model containing det. results
        file_ph : string
            CSV file containing results from stochastic solution
        stage : int
            Which stage to extract data for (1 or 2).
            1: only stage one investments included (default)
            2: both stage one and stage two investments included
        scenario : int
            which stage 2 scenario to get data for (only relevant when stage=2)
        newData : Boolean
            Choose whether to use only new data (True) or add new data to 
            existing data (False)
            
        Use either model or file_ph parameter        
        
        Returns
        =======
        GridData object reflecting optimal solution
        '''
        import copy

        grid_res = copy.deepcopy(grid_data)
        res_brC = pd.DataFrame(data=grid_res.branch['capacity']) 
        res_N = pd.DataFrame(data=grid_res.node['existing'])
        res_G = pd.DataFrame(data=grid_res.generator['pmax'])
        if newData:
            res_brC[res_brC>0] = 0
#            res_N[res_N>0] = 0
            res_G[res_G>0] = 0
            
        if model is not None:
            if stage == 1:
                for j in model.BRANCH:
                    res_brC['capacity'][j] += model.branchNewCapacity[j,stage].value
                for j in model.NODE:
                    res_N['existing'][j] += int(model.newNodes[j,stage].value)
                for j in model.GEN:
                    res_G['pmax'][j] += model.genNewCapacity[j,stage].value
            if stage >= 2:
                #add to investments in stage 1
                res_brC['capacity'] += grid_res.branch['capacity2']
                res_G['pmax'] += grid_res.generator['pmax2']
                for j in model.BRANCH:
                    res_brC['capacity'][j] += model.branchNewCapacity[j,stage].value
                for j in model.NODE:
                    res_N['existing'][j] += int(model.newNodes[j,stage].value)
                for j in model.GEN:
                    res_G['pmax'][j] += model.genNewCapacity[j,stage].value
        elif file_ph is not None:
            df_ph = pd.read_csv(file_ph,header=None,skipinitialspace=True,
                                names=['stage','node',
                                       'var','var_indx','value'])
            if stage==1:
                df_branchNewCapacity = df_ph[
                    (df_ph['var']=='branchNewCapacity') & 
                    (df_ph['stage']==stage)]
                df_newNodes = df_ph[
                    (df_ph['var']=='newNodes') & 
                    (df_ph['stage']==stage)]
                df_newGen = df_ph[
                    (df_ph['var']=='genNewCapacity') & 
                    (df_ph['stage']==stage)]
                for k,row in df_branchNewCapacity.iterrows():
                    res_brC['capacity'][int(row['var_indx'])] += float(row['value'])
                for k,row in df_newNodes.iterrows():
                    res_N['existing'][row['var_indx']] += int(row['value'])
                for k,row in df_newGen.iterrows():
                    res_G['pmax'][int(row['var_indx'])] += float(row['value'])                
            if stage>=2:
                if scenario is None:
                    raise Exception('Missing input "scenario"')
                res_brC['capacity'] += grid_res.branch['capacity2']
                res_G['pmax'] += grid_res.generator['pmax2']
                    
                df_branchNewCapacity = df_ph[
                    (df_ph['var']=='branchNewCapacity') &
                    (df_ph['stage']==stage) &
                    (df_ph['node']=='LeafNode_Scenario{}'.format(scenario))]
                df_newNodes = df_ph[(df_ph['var']=='newNodes') &
                    (df_ph['stage']==stage) &
                    (df_ph['node']=='LeafNode_Scenario{}'.format(scenario))]
                df_newGen = df_ph[(df_ph['var']=='genNewCapacity') &
                    (df_ph['stage']==stage) &
                    (df_ph['node']=='LeafNode_Scenario{}'.format(scenario))]

                for k,row in df_branchNewCapacity.iterrows():
                    res_brC['capacity'][int(row['var_indx'])] += float(row['value'])
                for k,row in df_newNodes.iterrows():
                    res_N['existing'][row['var_indx']] += int(row['value'])
                for k,row in df_newGen.iterrows():
                    res_G['pmax'][int(row['var_indx'])] += float(row['value'])                
        else:
            raise Exception('Missing input parameter')
            
        grid_res.branch['capacity'] = res_brC['capacity']
        grid_res.node['existing'] = res_N['existing']
        grid_res.generator['pmax'] = res_G['pmax']
        grid_res.branch = grid_res.branch[grid_res.branch['capacity'] 
            > self._NUMERICAL_THRESHOLD_ZERO]
        grid_res.node = grid_res.node[grid_res.node['existing'] 
            > self._NUMERICAL_THRESHOLD_ZERO]
        return grid_res
    
    def loadResults(self, filename):
        '''load results from excel into pandas dataframe'''
        df_res = pd.read_excel(filename)
        return df_res
        
        
        
def annuityfactor(rate,years):
    '''Net present value factor for fixed payments per year at fixed rate'''
    if rate==0:
        annuity = years
    else:
        annuity = (1-1/((1+rate)**years))/rate
    return annuity
        
            

def _TMPsample_kmeans(X, samplesize):
    """K-means sampling

    Parameters
    ==========
    X : matrix
        data matrix to sample from
    samplesize : int
        size of sample
        
    This method relies on sklearn.cluster.KMeans

    """
    """
    TODO: Have to weight the importance, i.e. multiply timeseries with
    installed capacities in order to get proper clustering. 
    """
    from sklearn.cluster import KMeans
    #from sklearn.metrics.pairwise import pairwise_distances_argmin
    #from sklearn.datasets.samples_generator import make_blobs
    
    n_clusters=samplesize
    k_means = KMeans(init='k-means++', n_clusters=n_clusters, n_init=10)
    k_means.fit(X)
    # which cluster nr it belongs to:
    k_means_labels = k_means.labels_    
    k_means_cluster_centers = k_means.cluster_centers_
    k_means_labels_unique, X_indecies = np.unique(k_means_labels, 
                                                  return_index=True)
    #k_means_predict = k_means.predict(X)
        
    return k_means_cluster_centers

    
def _TMPsample_mmatching(X, samplesize):
    """
    The idea is to make e.g. 10000 randomsample-sets of size=samplesize 
    from the originial datasat X. 
    
    Choose the sampleset with the lowest objective:
    MINIMIZE [(meanSample - meanX)^2 + (stdvSample - stdvX)^2...]
    
    in terms of stitistical measures
    """
    
    return


def _TMPsample_meanshift(X, samplesize):
    """M matching sampling

    Parameters
    ==========
    X : matrix
        data matrix to sample from
    samplesize : int
        size of sample
        
    This method relies on sklearn.cluster.MeanShift

    It is a centroid-based algorithm, which works by updating candidates 
    for centroids to be the mean of the points within a given region. 
    These candidates are then filtered in a post-processing stage to 
    eliminate near-duplicates to form the final set of centroids.
    """
    #from sklearn.cluster import MeanShift, estimate_bandwidth
    #from sklearn.datasets.samples_generator import make_blobs

    # The following bandwidth can be automatically detected using
    bandwidth = sklearn.cluster.estimate_bandwidth(X, quantile=0.2, 
                                                   n_samples=samplesize)
    
    ms = sklearn.cluster.MeanShift(bandwidth=bandwidth, bin_seeding=True)
    ms.fit(X)
    #labels = ms.labels_
    cluster_centers = ms.cluster_centers_
    
    #labels_unique = np.unique(labels)
    #n_clusters_ = len(labels_unique)
    
    #print("number of estimated clusters : %d" % n_clusters_)
    
    return cluster_centers


def _TMPsample_latinhypercube(X, samplesize):
    """Latin hypercube sampling

    Parameters
    ==========
    X : matrix
        data matrix to sample from
    samplesize : int
        size of sample
        
    This method relies on pyDOE.lhs(n, [samples, criterion, iterations])

    """
    """
    lhs(n, [samples, criterion, iterations])
    
    n:an integer that designates the number of factors (required)
    samples: an integer that designates the number of sample points to generate 
        for each factor (default: n) 
    criterion: a string that tells lhs how to sample the points (default: None,  
        which simply randomizes the points within the intervals):
        “center” or “c”: center the points within the sampling intervals
        “maximin” or “m”: maximize the minimum distance between points, but place 
                          the point in a randomized location within its interval
        “centermaximin” or “cm”: same as “maximin”, but centered within the intervals
        “correlation” or “corr”: minimize the maximum correlation coefficient
    """
    from pyDOE import lhs
    from scipy.stats.distributions import norm
    X_rows = X.shape[0]; X_cols = X.shape[1]
    X_mean = X.mean(); X_std = X.std()
    X_sample = lhs( X_cols , samples=samplesize , criterion='center' )
    kernel=False
    if kernel:
        # Fit data w kernel density
        from sklearn.neighbors.kde import KernelDensity
        kde = KernelDensity(kernel='gaussian', bandwidth=0.2).fit(X)
        kde.score_samples(X)
        # random sampling (TODO: fit to latin hypercube sample):
        kde_sample = kde.sample(samplesize)     
    else:
        # Fit data w normal distribution
        for i in range(X_cols):
            X_sample[:,i] = norm(loc=X_mean[i] , scale=X_std[i]).ppf(X_sample[:,i])
    
    return X_sample
  
def sampleProfileData(data, samplesize, sampling_method):
        """ Sample data from full-year time series
        
        Parameters
        ==========
        data : GridData object
            Sample from data.profiles
        samplesize : int
            size of sample
        sampling_method : str
            'kmeans', 'uniform', 
            EXPERIMENTAL: 'kmeans_scale', 'lhs',  ('mmatching', 'meanshift')
            
        
        Returns
        =======
            reduced data matrix according to sample size and method
        
        
        
        """
        
        """
        Harald:
        TODO: Tidy up - remove irrelevant code.
        -Note: Profiles may also include generator cost profile, not only
        generation and consumption
        -Should we cluster the profiles, or all consumers and generators? This
        is different sine many generators/consumers may use the same profile.
        Using all generators/consumers is more difficult, but probably more 
        correct
        -How to determine weight between different types of variations, i.e.
        generation/consumption (MW) vs marginal costs (€)? Using normalised
        profiles with no weighing is one such choice.
        """
        
        X = data.profiles.copy()
        
        if sampling_method == 'kmeans':
            """
            Harald preferred method:            
            Scale all profiles to have similar variability, 
            then cluster, and finally scale back
            """
            # Consider only those profiles which are used in the model:
            profiles_in_use = data.generator['inflow_ref'].append(
                data.generator['fuelcost_ref']).append(
                data.consumer['demand_ref']).unique().tolist()
            X = X[profiles_in_use]

            #scaler = sklearn.preprocessing.MinMaxScaler()
            scaler = sklearn.preprocessing.RobustScaler()
            x_scaled = scaler.fit_transform(X)
            X = pd.DataFrame(data=x_scaled, columns=X.columns, 
                          index=X.index)
            km_norm2=sklearn.cluster.KMeans(n_clusters=samplesize,
                                            init='k-means++')
            km_norm2.fit(X)
            km_orig=scaler.inverse_transform(km_norm2.cluster_centers_)
            X_sample = pd.DataFrame(data=km_orig,columns=X.columns)
            return X_sample

        elif sampling_method == 'kmeans_scale':
            print("Using k-means with scaled profiles -> IN PROGRESS")
            #TODO: How to scale prices?
            # Multiply time series for load and VRES with their respective 
            # maximum capacities in order to get the correct clusters/samples

            for k in data.profiles.columns.values.tolist():
                ref = k
                pmax = sum(data.generator.pmax[g] for g in range(len(data.generator)) if data.generator.inflow_ref[g] == ref)
                if pmax > 0:
                    X[ref] = data.profiles[ref] * pmax
#            for k,row in self.generator.iterrows():
#                pmax = row['pmax']
#                ref = row['inflow_ref']
#                if X[ref].mean()<1:
#                    X[ref] = self.profiles[ref] * pmax
            X['const'] = 1
            
            for k,row in data.consumer.iterrows():
                pmax = row['demand_avg']
                ref = row['demand_ref']
                X[ref] = data.profiles[ref] * pmax
                
                X_sample = _TMPsample_kmeans(X, samplesize)
                X_sample = pd.DataFrame(data=X_sample,
                        columns=X.columns)

            # convert back to relative values
            for k in data.profiles.columns.values.tolist():
                ref = k
                pmax = sum(data.generator.pmax[g] for g in range(len(data.generator)) if data.generator.inflow_ref[g] == ref)
                if pmax > 0:
                    X_sample[ref] = X_sample[ref] / pmax
#            for k,row in self.generator.iterrows():
#                pmax = row['pmax']
#                ref = row['inflow_ref']
#                if pmax == 0:
#                    centroids[ref] = 0
#                else:
#                    if X[ref].mean()>1:
#                        centroids[ref] = centroids[ref] / pmax
            for k,row in data.consumer.iterrows():
                pmax = row['demand_avg']
                ref = row['demand_ref']
                if pmax == 0:
                    X_sample[ref] = 0
                else:
                    X_sample[ref] = X_sample[ref] / pmax
            X_sample['const'] = 1
            return X_sample

        elif sampling_method == 'mmatching':
            print("Using moment matching... -> NOT IMPLEMENTED")
        elif sampling_method == 'meanshift':
            print("Using Mean-Shift... -> EXPERIMENTAL")
            X_sample = _TMPsample_meanshift(X, samplesize)
            return X_sample
        elif sampling_method == 'lhs':
            print("Using Latin-Hypercube... -> EXPERIMENTAL")
            X_sample = _TMPsample_latinhypercube(X, samplesize)
            X_sample = pd.DataFrame(data=X_sample,
                        columns=X.columns)
            X_sample['const'] = 1
            X_sample[(X_sample < 0)] = 0
            return X_sample
        elif sampling_method == 'uniform':
            print("Using uniform sampling (consider changing sampling method!)...")
            #Use numpy random in order to have control of ranom seed from
            # top level script (np.random.seed(..))
            timerange=pd.np.random.choice(data.profiles.shape[0],
                                        size=samplesize,replace=False)

            #timerange = random.sample(range(8760),samplesize)
            X_sample = data.profiles.loc[timerange, :]
            X_sample.index = list(range(len(X_sample.index)))
            return X_sample
        else:
            raise Exception("Unknown sampling method")                     
        return
        
        
        
        
class CostBenefit(object):
    '''
    Experimental class for cost-benefit calculations. 
    
    Currently including allocation schemes based on "cooperative game theory"
    '''

    
    def __init__(self):
        """Collect value-functions for each player in the expansion-game
        
        Parameters
        ----------
        
        
        Creat CostBenefit object:
        """
        self.players = None
        self.coalitions = None
        self.valueFunction = None
        self.payoff = None

    def power_set(self,List):
        """
        function to return the powerset of a list, i.e. all possible subsets ranging
        from length of one, to the length of the larger list
        """
        from itertools import combinations
        
        subs = [list(j) for i in range(len(List)) for j in combinations(List, i+1)]
        return subs  
                
    def nCr(self,n,r):
        '''
        calculate the binomial coefficient, i.e. how many different possible 
        subsets can be made from the larger set n
        '''
        import math
        f = math.factorial
        return f(n) / f(r) / f(n-r)
        
    
    def gameSetup(self, grid_data):    
        self.players = grid_data.node.area.unique().tolist()
        self.coalitions = self.power_set(self.players)
        
        
    def getBinaryCombinations(self,num):
        '''
        Returns a sequence of different combinations 1/0 for a number of
        decision variables. E.g. three cable investments;
        (0,0,0), (1,0,0), (0,1,0), and so on. 
        '''
        import itertools
        combinations = list(itertools.product([0,1], repeat=num))
        return combinations

        
    def gameShapleyValue(self,player_list, values):
        '''compute the Shapley Value from cooperative game theory
       
       Parameters:
        ===========
        player_list: list of all players in the game
        values: characteristic function for each subset of N players, i.e. 
                possible coaltions/cooperations among players.
                
        Returns the Shapley value, i.e. a fair cost/benefit allocation based
        on the average marginal contribution from each player. 
        
        '''
                    
        if type(values) is not dict:
            raise TypeError("characteristic function must be a dictionary")
        for key in values:
            if len(str(key)) == 1 and type(key) is not tuple:
                values[(key,)] = values.pop(key)
            elif type(key) is not tuple:
                raise TypeError("key must be a tuple")
        for key in values:
            sortedkey = tuple(sorted(list(key)))
            values[sortedkey] = values.pop(key)
    
        player_list = max(values.keys(), key=lambda key: len(key))
        for coalition in self.power_set(player_list):
            if tuple(sorted(list(coalition))) not in sorted(values.keys()):
                raise ValueError("characteristic function must be the power set")
        
        payoff_vector = {}
        n = len(player_list)
        for player in player_list:
            weighted_contribution = 0
            for coalition in self.power_set(player_list):
                if coalition:  # If non-empty
                    k = len(coalition)
                    weight = 1/(self.nCr(n,k)*k)
                    t = tuple(p for p in coalition if p != player)
                    weighted_contribution += weight * (values[tuple(coalition)]
                                                       - values[t])
            payoff_vector[player] = weighted_contribution
    
        return payoff_vector
            
    def gameIsMonotone(self, values):        
        '''
        Returns true if the game/valueFunction is monotonic.
        A game G = (N, v) is monotonic if it satisfies the value function
        of a subset is less or equal then the value function from its
        union set:
        v(C_2) \geq v(C_1) for all C_1 \subseteq C_2
        '''
        import itertools
        return not any([set(p1) <= set(p2) and values[p1] > values[p2]
            for p1, p2 in itertools.permutations(values.keys(), 2)])
    
        
    def gameIsSuperadditive(self, values):
        '''
        Returns true if the game/valueFunction is superadditive.
        A characteristic function game G = (N, v) is superadditive
        if it the sum of two coalitions/subsets gives a larger value than the 
        individual sum:
        v(C_1 \cup C_2) \geq v(C_1) +  v(C_2) for
        all C_1, C_2 \subseteq 2^{\Omega} such that C_1 \cap C_2
        = \emptyset.
        '''
        import itertools
        sets = values.keys()
        for p1, p2 in itertools.combinations(sets, 2):
            if not (set(p1) & set(p2)):
                union = tuple(sorted(set(p1) | set(p2)))
                if values[union] < values[p1] + values[p2]:
                    return False
        return True            
    
    def gamePayoffIsEfficient(self, player_list, values, payoff_vector):
        '''
        Return `true if the payoff vector is efficient. A payoff vector v is 
        efficient if the sum of payments equal the total value provided by a 
        set of players. 
        \sum_{i=1}^N \lambda_i = v(\Omega);
        '''
        pl = tuple(sorted(list(player_list)))
        return sum(payoff_vector.values()) == values[pl]
    
    def gamePayoffHasNullplayer(self, player_list, values, payoff_vector):
        '''
        Return true if the payoff vector possesses the nullplayer property.
        A payoff vector v has the nullplayer property if there exists
        an i such that v(C \cup i) = v(C) for all C \in 2^{\Omega}
        then, \lambda_i = 0. In other words: if a player does not
        contribute to any coalition then that player should receive no payoff.
        '''
        for player in player_list:
            results = []
            for coalit in values:
                if player in coalit:
                    t = tuple(sorted(set(coalit) - {player}))
                    results.append(values[coalit] == values[t])
            if all(results) and payoff_vector[player] != 0:
                return False
        return True
    
    def gamePayoffIsSymmetric(self, values, payoff_vector):
        '''
        Returns true if the resulting payoff vector possesses the symmetry property.
        A payoff vector possesses the symmetry property if players with equal
        marginal contribution receives the same payoff:
        v(C \cup i) = v(C \cup j) for all
        C \in 2^{\Omega} \setminus \{i,j\}, then x_i = x_j.
        '''
        import itertools
        sets = values.keys()
        element = [i for i in sets if len(i) == 1]
        for c1, c2 in itertools.combinations(element, 2):
            results = []
            for m in sets:
                junion = tuple(sorted(set(c1) | set(m)))
                kunion = tuple(sorted(set(c2) | set(m)))
                results.append(values[junion] == values[kunion])
            if all(results) and payoff_vector[c1[0]] != payoff_vector[c2[0]]:
                return False
        return True
        
        
class Results(object):
    '''
    Temporary class for processing result data in PowerGIM


    Parameters
    ----------
    grid : GridData
        PowerGIM GridData object
    resultfile : string
        name of excel file for storage of results

    '''  
    
    def __init__(self,grid,resultfile):
        '''
        Create a PowerGIM Results object
            
        '''
        self.grid = grid
        self.timerange = grid.timerange
        self.results = resultfile
        
        return


    def plotMapGrid(self,nodetype=None,branchtype=None,dcbranchtype=None,
                    show_node_labels=False,branch_style='c',latlon=None,
                    timeMaxMin=None,
                    dotsize=40, filter_node=None, filter_branch=None,
                    draw_par_mer=False,showTitle=True, colors=True):
        '''
        Plot results to map
        
        Parameters
        ----------
        nodetype : string
            "", "area", "nodalprice", "energybalance", "loadshedding"
        branchtype : string
            "", "capacity", "area", "utilisation", "flow", "sensitivity"
        dcbranchtype : string
            "", "capacity"
        show_node_labels : boolean
            whether to show node names (true/false)
        branch_style : string or list of strings (optional)
            How branch capacity and flow should be visualised. 
            "c" = colour, "t" = thickness. The two options may be combined.
        dotsize : integer (optional)
            set dot size for each plotted node
        latlon: list of four floats (optional)
            map area [lat_min, lon_min, lat_max, lon_max]
        filter_node : list of two floats (optional)
            [min,max] - lower and upper cutoff for node value
        filter_branch : list of two floats
            [min,max] - lower and upper cutoff for branch value
        draw_par_mer : boolean
            whether to draw parallels and meridians on map 
        showTitle : boolean
        colors : boolean
            Whether to use colours or not 
        '''
        
        # basemap is only used here, so to allow using powergama without
        # basemap installed, it is best to put import statement here.
        from mpl_toolkits.basemap import Basemap

        if timeMaxMin is None:
            timeMaxMin = [self.timerange[0],self.timerange[-1]+1]

        plt.figure()
        data = self.grid
        #res = self
        
        if latlon is None:
            lat_max =  max(data.node.lat)+1
            lat_min =  min(data.node.lat)-1
            lon_max =  max(data.node.lon)+1
            lon_min =  min(data.node.lon)-1
        else:
            lat_min = latlon[0]
            lon_min = latlon[1]
            lat_max = latlon[2]
            lon_max = latlon[3]
        
        # Use the average latitude as latitude of true scale
        lat_truescale = np.mean(data.node.lat)
                
        m = Basemap(resolution='l',projection='merc',\
                      lat_ts=lat_truescale, \
                      llcrnrlon=lon_min, llcrnrlat=lat_min,\
                      urcrnrlon=lon_max ,urcrnrlat=lat_max, \
                      anchor='W')
         
        # Draw coastlines, meridians and parallels.
        m.drawcoastlines()
        #m.drawcountries(zorder=0)
        
        if colors:
            m.fillcontinents(color='coral',lake_color='aqua',zorder=0)
            m.drawmapboundary(fill_color='aqua')
        else:
            m.fillcontinents(zorder=0)
            m.drawmapboundary()
        
        if draw_par_mer:
            m.drawparallels(np.arange(_myround(lat_min,10,'floor'),
                _myround(lat_max,10,'ceil'),10),
                labels=[1,1,0,0])

            m.drawmeridians(np.arange(_myround(lon_min,10,'floor'),
                _myround(lon_max,10,'ceil'),10),
                labels=[0,0,0,1])
                
        


        # AC Branches
        num_branches = data.branch.shape[0]
        
        lwidths = [2]*num_branches
        
        # default values:
        branch_value = np.asarray([0.5]*num_branches)
        branch_colormap = cm.gray
        branch_plot_colorbar = True
        
        if branchtype=='area':
            areas = data.node.area
            allareas = data.getAllAreas()
            branch_value = [-1]*num_branches
            nodes_from = data.branchFromNodeIdx()
            nodes_to = data.branchToNodeIdx()
            for i in range(num_branches):
                #node_indx_from = data.node.name.index(data.branch.node_from[i])
                #node_indx_to = data.node.name.index(data.branch.node_to[i])
                area_from = areas[nodes_from[i]]
                area_to = areas[nodes_to[i]]
                if area_from == area_to:
                    branch_value[i] = allareas.index(area_from)
                branch_value = np.asarray(branch_value)
#            branch_colormap = plt.get_cmap('hsv')
            branch_colormap = cm.prism
            branch_colormap.set_under('k')
            filter_branch = [0,len(allareas)]
            branch_label = 'Branch area'
            branch_plot_colorbar = False
        elif branchtype=='utilisation':
            utilisation = self.getAverageUtilisation(timeMaxMin)
            branch_value = utilisation
            branch_colormap = plt.get_cmap('hot')
            branch_label = 'Branch utilisation'
        elif branchtype=='capacity':         
            cap = data.branch.capacity
            branch_plot_colorbar = False
            branch_label = 'Branch capacity'
            if 'c' in branch_style:
                branch_value = np.asarray(cap)
                branch_colormap = plt.get_cmap('hot')
                branch_plot_colorbar = True
                if filter_branch is None:
                    # need an upper limit to avoid crash due to inf capacity
                    maxcap = np.nanmax(branch_value)
                    filter_branch = [0,np.round(maxcap,-2)+100]
            if 't' in branch_style:
                avgcap = np.mean(cap)
                if avgcap == 0:
                    lwidths = [0 for f in cap]  
                else:
                    lwidths = [2*f/avgcap for f in cap]  
        elif branchtype=='flow':
            avgflow = self.getAverageBranchFlows(timeMaxMin)[2]
            if 'c' in branch_style:
                branch_value = np.asarray(avgflow)
                branch_colormap = plt.get_cmap('hot')
            else:
                branch_plot_colorbar = False
            if 't' in branch_style:
                avgavgflow = np.mean(avgflow)
                lwidths = [2*f/avgavgflow for f in avgflow]        
            branch_label = 'Branch flow'
            #branch_value = np.asarray(avgflow)
            #branch_colormap = plt.get_cmap('hot')
        elif branchtype=='sensitivity':
            branch_value = np.zeros(num_branches)
            avgsense = self.getAverageBranchSensitivity(timeMaxMin)
            branch_value[self.idxConstrainedBranchCapacity] = -avgsense
            branch_colormap = plt.get_cmap('hot')
            branch_label = 'Branch sensitivity'
            # These sensitivities are mostly negative 
            # (reduced cost by increasing branch capacity)
            #minsense = np.nanmin(avgsense)
            #maxsense = np.nanmax(avgsense)
        else:
            branch_value = np.asarray([0.5]*num_branches)
            branch_colormap = cm.gray
            branch_plot_colorbar = False
        
        idx_from = data.branchFromNodeIdx()
        idx_to = data.branchToNodeIdx()
        branch_lat1 = [data.node.lat[i] for i in idx_from]        
        branch_lon1 = [data.node.lon[i] for i in idx_from]        
        branch_lat2 = [data.node.lat[i] for i in idx_to]        
        branch_lon2 = [data.node.lon[i] for i in idx_to]

        x1, y1 = m(branch_lon1,branch_lat1)
        x2, y2 = m(branch_lon2,branch_lat2)

        ls = [[(x1[i],y1[i]),(x2[i],y2[i])] for i in range(len(x1))]
        #ls = [[(x1[i],y1[i]),(x2[i],y2[i])] for i in range(num_branches)]
        ax=plt.axes()    
        if not lwidths:
            print("No new data")
        else:
            line_segments_ac = mpl.collections.LineCollection(
                    ls, linewidths=lwidths,cmap=branch_colormap)
        
            if filter_branch is not None:
                line_segments_ac.set_clim(filter_branch)
            line_segments_ac.set_array(branch_value)
            ax.add_collection(line_segments_ac)
      

        # DC Branches
        lwidths = [2] * 1
        #lwidths = [2] * num_dcbranches
        if dcbranchtype is not None:
            branch_plot_colorbar = False
            branch_value = np.asarray([0.1] * num_branches)
            branch_colormap = cm.winter
        
        if dcbranchtype == 'flow':
            avgTot = self.getAverageBranchFlows(timeMaxMin,False)[2]
            if 'c' in branch_style:
                branch_value = np.asarray(avgTot)
                branch_colormap = plt.get_cmap('hot')
                branch_plot_colorbar = True
            if 't' in branch_style:
                avgavgflow = np.mean(avgTot)
                lwidths = [2*f/avgavgflow for f in avgTot]        
            branch_label = 'Branch flow'
        elif dcbranchtype == 'capacity':
            cap = [data.branch.capacity[i] for i in range(len(data.branch.capacity)) if data.branch.type[i] == 'dc']
            branch_value = np.asarray(cap)
            maxcap = np.nanmax(branch_value)
            branch_colormap = plt.get_cmap('hot')
            branch_label = 'Branch capacity'
            if filter_branch is None:
                # need an upper limit to avoid crash due to inf capacity
                filter_branch = [0,np.round(maxcap,-2)+100]
            if 't' in branch_style:
                avgcap = np.mean(cap)
                lwidths = [2*f/avgcap for f in cap]  
            
        idx_from = data.dcBranchFromNodeIdx()   # empty
        idx_to = data.dcBranchToNodeIdx()       # empty
        branch_lat1 = [data.node.lat[i] for i in idx_from]        
        branch_lon1 = [data.node.lon[i] for i in idx_from]        
        branch_lat2 = [data.node.lat[i] for i in idx_to]        
        branch_lon2 = [data.node.lon[i] for i in idx_to]

        x1, y1 = m(branch_lon1,branch_lat1)
        x2, y2 = m(branch_lon2,branch_lat2)
        ls = [[(x1[i],y1[i]),(x2[i],y2[i])] for i in range(len(x1))]
        line_segments_dc = mpl.collections.LineCollection(
                ls, linewidths=lwidths,colors='black')
        #line_segments_dc = mpl.collections.LineCollection(
        #        ls, linewidths=2,colors='blue')
        if filter_branch is not None:
            line_segments_dc.set_clim(filter_branch)
        line_segments_dc.set_array(branch_value)
        ax.add_collection(line_segments_dc)
        
        # Nodes
        node_plot_colorbar = True
        if nodetype=='area':
            areas = data.node.area
            allareas = data.getAllAreas()
            #colours_co = cm.prism(np.linspace(0, 1, len(allareas)))
            node_label = 'Node area'
            node_value = [allareas.index(c) for c in areas]
            node_colormap = cm.prism
            node_plot_colorbar = False
            # this is to get same colours as for branches:
            node_colormap.set_under('k')
            filter_node = [0,len(allareas)]
        elif nodetype=='nodalprice':
            avgprice = self.getAverageNodalPrices(timeMaxMin)
            node_label = 'Nodal price'
            node_value = avgprice
            node_colormap = cm.jet
        elif nodetype=='lmp':
            node_value = self.getAverageNodalPrices(timeMaxMin)
            node_label = 'Locational marginal price'
            node_colormap = cm.jet
        elif nodetype=='energybalance':
            avg_energybalance = self.getAverageEnergyBalance(timeMaxMin)
            node_label = 'Nodal energy balance'
            node_value = avg_energybalance
            node_colormap = cm.hot
        elif nodetype=='loadshedding':
            node_value = self.getLoadsheddingPerNode(timeMaxMin)
            node_label = 'Loadshedding'
            node_colormap = cm.hot
        else:
            node_value = 'dimgray'
            node_colormap = cm.jet
            node_label = ''
            node_plot_colorbar  = False
        

        x, y = m(data.node['lon'].tolist(),data.node['lat'].tolist())
        if nodetype=='lmp':
            sc = plt.hexbin(x, y, gridsize=20, C=node_value, 
                            cmap=node_colormap)
        else:
            sc=m.scatter(x,y,marker='o',c=node_value, cmap=node_colormap,
                         zorder=2,s=dotsize)            
        #sc.cmap.set_under('dimgray')
        #sc.cmap.set_over('dimgray')
        if filter_node is not None:
            sc.set_clim(filter_node[0], filter_node[1])
            
            # #TODO: Er dette nødvendig lenger, Harald?
            # #nodes with NAN nodal price plotted in gray:
            # for i in range(len(avgprice)):
                # if np.isnan(avgprice[i]):
                    # m.scatter(x[i],y[i],c='dimgray',
                              # zorder=2,s=dotsize)
        
        
        #NEW Colorbar for nodes
        # m. or plt.?
        if node_plot_colorbar:
            axcb2 = plt.colorbar(sc)
            axcb2.set_label(node_label)

        #NEW Colorbar for branch capacity
        if branch_plot_colorbar:
            axcb = plt.colorbar(line_segments_ac)
            axcb.set_label(branch_label)


        # Show names of nodes
        if show_node_labels:
            labels = data.node['id']
            x1,x2,y1,y2 = plt.axis()
            offset_x = (x2-x1)/50
            for label, xpt, ypt in zip(labels, x, y):
                if xpt > x1 and xpt < x2 and ypt > y1 and ypt < y2:
                    plt.text(xpt+offset_x, ypt, label)
        
        if showTitle:
            plt.title('Nodes %s and branches %s' %(nodetype,branchtype))
        plt.show()
                
        return